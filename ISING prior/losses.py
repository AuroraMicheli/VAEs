#%%
import torch
import torch.nn.functional as F
import numpy as np
from src.encoders_decoders import *
# %%
### Categorical latent space 

#SIMPLIFIED LOSS
def simplified_loss(x,decoder):
    # Compute loss function of MoG decoder in the ideal case of optimal encoder
    # given the decoder , as log(Σ_j q_j q(x|j))
    inv_sigma2 = torch.exp(-2*decoder.log_sigmas.transpose(0,1)) #[1,N]
    mp = decoder.mus.transpose(0,1)*inv_sigma2
    # x has shape [bsize,1]d
    logq_x_j = -0.5*(x**2)*inv_sigma2 + x*mp - 0.5*mp*decoder.mus.transpose(0,1)-\
    np.log(np.sqrt(2*np.pi)) -decoder.log_sigmas.transpose(0,1) +\
    F.log_softmax(decoder.qs.transpose(0,1),dim=1)
    logZ = -torch.logsumexp(logq_x_j,dim=1)
    return logZ.mean() 

def simplified_loss_orig(x,decoder):
    #Once we plug the expression for the encoder in the loss we have to minimize 
    #E_x [log(sum_j q(j)q(x|j))]
    inv_sigma2 = 1/(decoder.sigma.transpose(0,1))**2
    mp = decoder.mu.transpose(0,1)*inv_sigma2
    q_x_j = -0.5*(x**2)@inv_sigma2 + (x@mp) - 0.5*(mp)*(decoder.mu.transpose(0,1)) -torch.log(np.sqrt(2*np.pi)*decoder.sigma.transpose(0,1)) + torch.log(F.softmax(decoder.q,dim=1))
#logZ = torch.log((F.softmax(decoder.q,dim=1)*q_x_j).sum(dim=1))
    logZ = -torch.logsumexp(q_x_j,dim=1)
    return logZ.mean()

#Non ideal encoder
# DISTORTION 
def distortion_cat(x,encoder,decoder):
    # E_x[ sum_j p(j|x)*log(q(x|j))]
    p_j_x = F.softmax(encoder(x),dim=1)
    #Compute log(q(x|j))
    inv_sigma2 =torch.exp(-2*(decoder.log_sigmas.transpose(0,1)))
    mp = decoder.mus.transpose(0,1)*inv_sigma2
    logq_x_j = -0.5*(x**2)*inv_sigma2 + x*mp - 0.5*mp*decoder.mus.transpose(0,1)-\
     np.log(np.sqrt(2*np.pi))-decoder.log_sigmas.transpose(0,1)
    D = -((p_j_x*logq_x_j).sum(dim=1)).mean()
    return D

def distortion_cat_orig(x,encoder,decoder):
    p_j_x = encoder(x)
    inv_sigma2 = 1/(decoder.sigma.transpose(0,1))**2
    mp = (decoder.mu.transpose(0,1)*inv_sigma2)
    logq_x_j = -0.5*(x**2)@inv_sigma2 + (x@mp) - 0.5*(mp)*(decoder.mu.transpose(0,1))-torch.log(np.sqrt(2*np.pi)*decoder.sigma.transpose(0,1))
    loss = -((F.softmax(p_j_x))*logq_x_j).sum(dim=1).mean()
    return loss


#RATE
def rate_cat(x,encoder,decoder):
    p_tilde = encoder(x)
    R = (F.softmax(p_tilde,dim=1)*(F.log_softmax(p_tilde,dim=1)-\
    F.log_softmax(decoder.qs.transpose(0,1),dim=1))).sum(dim=1).mean()
    return R


def rate_cat_orig(x,encoder,decoder):
    p_j_x = encoder(x)
    dkl = ((F.softmax(p_j_x))*(F.log_softmax(p_j_x) - F.log_softmax(decoder.q))).sum(dim=1).mean() 
    return dkl

#MSE
def MSE_cat(x,decoder,encoder):
    # MSE is obtained as Σ_j p(j|x) ((x-μ_j)^2 + σ^2_j)
    if encoder is None:
        encoder = CategoricalEncoder(decoder.mus.transpose(0,1),\
        torch.exp(decoder.log_sigmas).transpose(0,1),decoder.qs.transpose(0,1))
    l_j_x = encoder(x)
    mse = (F.softmax(l_j_x,dim=1)*((x-decoder.mus.transpose(0,1))**2 + 
    torch.exp(2*decoder.log_sigmas.transpose(0,1)))).sum(dim=1).mean()
    return mse
# %%
#Bernoulli latent space

def MSE_cat_orig(x,encoder,decoder):
    p_j_x = encoder(x)
    mse = ((F.softmax(p_j_x))*(x**2 + decoder.mu.transpose(0,1)**2 -2*x*decoder.mu.transpose(0,1) + decoder.sigma.transpose(0,1)**2)).sum(dim=1).mean()
    return mse



def distortion_gaussian(x,encoder,decoder,lat_samp=10,tau=0.5):
    #Logit r|x
    l_r_x = encoder(x)
    bsize,N = l_r_x.shape
    eps = torch.rand(bsize,lat_samp,N)
    r = torch.sigmoid((torch.log(eps) - torch.log(1-eps) + l_r_x[:,None,:])/tau)
    mu_dec,sigma2_dec = decoder(r)
    inv_sigma2_dec = 1/sigma2_dec
    mp = mu_dec*inv_sigma2_dec
    logq_x_r = -0.5*(x**2)*inv_sigma2_dec + x*mp - 0.5*mu_dec*mp -\
    0.5*torch.log(2*np.pi*sigma2_dec)
    D = -logq_x_r.mean()
    return D
##
def distortion_ideal(x,encoder,lat_samp=10,tau=0.5):
    l_r_x = encoder(x)
    bsize,N = l_r_x.shape
    eps = torch.rand(bsize,lat_samp,N)
    r = torch.sigmoid((torch.log(eps) - torch.log(1-eps) + l_r_x[:,None,:])/tau)
    lam = encoder(x).transpose(0,1)
    b = -torch.log(torch.exp(encoder(x))+1).transpose(0,1).sum(dim=0)[None,None,:]
    h = torch.softmax(r@lam + b,dim=2)
    D = torch.cat([-torch.log(h[i,:,i]) for i in range(bsize)]).mean()
    return D
##
def rate_iidBernoulli(x,encoder,p_q):
    l_r_x = encoder(x)
    R = (torch.sigmoid(l_r_x)*(F.logsigmoid(l_r_x) - np.log(p_q)) + torch.sigmoid(-l_r_x)*(F.logsigmoid(-l_r_x) - np.log(1-p_q))).sum(dim=1).mean()
    return R
def rate_vampBernoulli(x,encoder,x_k):
    #x_k = x_sorted[random.sample(range(500),K)]
    l_r_x = encoder(x_sorted)[:,:,None]
    l_r = encoder(x_k).transpose(0,1)[None,:,:]
    KLs = (torch.sigmoid(l_r_x)*(F.logsigmoid(l_r_x) - F.logsigmoid(l_r)) + torch.sigmoid(-l_r_x)*  (F.logsigmoid(-l_r_x) - F.logsigmoid(-l_r))).sum(dim=1)
    R = -torch.logsumexp(-KLs-np.log(K),dim=1).mean()
    return R
##
def MSE_montecarlo(x,encoder,decoder,lat_samp =10,dec_samp=10):
    r = encoder.sample(x,lat_samp)
    x_dec = decoder.sample(r,dec_samp)
    mseVec = ((x_dec - x[None,:])**2).mean(dim=(0,2))
    return mseVec.mean()
