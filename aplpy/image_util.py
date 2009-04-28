import scipy.ndimage as ndimage
import scipy.interpolate as interpolate
import numpy as np

import math_util

def resample(array,factor):
    nx,ny = np.shape(array)
    nx_new = nx / factor
    ny_new = ny / factor
    array2 = np.empty((nx_new,ny))
    for i in range(nx_new-1):
        array2[i,:] = np.sum(array[i*factor:i*factor+1,:],axis=0)
    
    array3 = np.empty((nx_new,ny_new))
    for j in range(ny_new-1):
        array3[:,j] = np.sum(array2[:,j*factor:j*factor+1],axis=1)
    
    return array3

def smooth(array,sigma):
    ndimage.gaussian_filter(array,sigma=sigma)

def percentile_function(array):
    
    array = array.ravel()
    array = array[np.where(np.isnan(array)==False)]
    
    n_total  = np.shape(array)[0]
    array = np.sort(array)
    
    x = np.arange(0.,n_total,1.)
    x = x / float(n_total-1)
    
    spl = interpolate.interp1d(x=x,y=array)
    
    if n_total > 10000:
        x = math_util.complete_range(0.,1.,10000)
        spl = interpolate.interp1d(x=x,y=spl(x))
    
    array = None
    
    return spl

def stretch(array, function, exponent=2, midpoint=0.5):
        
    if function is 'linear':
        return array
    elif function is 'log':
        return np.log10(array/midpoint+1.) / np.log10(1./midpoint+1.)
    elif function is 'sqrt':
        return np.sqrt(array)
    elif function is 'arcsinh':
        return np.arcsinh(array/midpoint) / np.arcsinh(1./midpoint)
    elif function is 'power':
        return np.power(array, exponent)
    else:
        raise Exception("Unknown function : " + function)
