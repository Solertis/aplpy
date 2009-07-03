from distutils import version
import os

try:
    import matplotlib
    import matplotlib.pyplot as mpl
except ImportError:
    raise Exception("matplotlib is required for APLpy")

if version.LooseVersion(matplotlib.__version__) < version.LooseVersion('0.98.5.2'):
    print '''
WARNING : matplotlib >= 0.98.5.2 is recommended for APLpy. Previous
          versions of matplotlib contain bugs which may affect APLpy.
          This is just a warning, and you may continue to use APLpy.
          '''

try:
    # this requires at least revision 7084 of matplotlib toolkits
    import mpl_toolkits.axes_grid.parasite_axes as mpltk
    # hardcode as False for the moment
    axesgrid = True
except ImportError:
    axesgrid = False

if axesgrid:
    print '''
WARNING: you appear to be using the svn version of matplotlib. Some features
         are only enabled with this version, but you need to make sure that
         you are using at least revision 7097 of matplotlib (Friday 8th May
         2009), or you may encounter problems (note that this warning will
         appear even if you do have the latest version).
'''

try:
    import pyfits
except ImportError:
    raise Exception("pyfits is required for APLpy")

try:
    import pywcs
except ImportError:
    raise Exception("pywcs is required for APLpy")

import contour_util

import numpy as np

import montage
import image_util
import header
import wcs_util
import math_util as m

from layers import Layers
from grid import Grid
from ticks import Ticks
from labels import Labels

class FITSFigure(Layers,Grid,Ticks,Labels):
    
    "A class for plotting FITS files."
    
    def __init__(self,data,hdu=0,figure=None,subplot=None,downsample=False,north=False,**kwargs):
        '''
        Create a FITSFigure instance
        
        Required arguments:
            
            *data*: [ string | pyfits PrimaryHDU | pyfits ImageHDU ]
                Either the filename of the FITS file to open, or a pyfits
                PrimaryHDU or ImageHDU instance.
        
        Optional Keyword Arguments:
            
            *hdu*: [ integer ]
                By default, the image in the primary HDU is read in. If a
                different HDU is required, use this argument.
            
            *figure*: [ matplotlib figure() instance ]
                If specified, a subplot will be added to this existing
                matplotlib figure() instance, rather than a new figure
                being created from scratch.
            
            *subplot*: [ list of four floats ]
                If specified, a subplot will be added at this position. The
                list should contain [xmin, ymin, dx, dy] where xmin and ymin
                are the position of the bottom left corner of the subplot, and
                dx and dy are the width and height of the subplot respectively.
                These should all be given in units of the figure width and
                height. For example, [0.1,0.1,0.8,0.8] will almost fill the
                entire figure, leaving a 10 percent margin on all sides.
                Note: this requires matplotlib 0.98.6
            
            *downsample*: [ integer ]
                If this option is specified, the image will be downsampled
                by a factor *downsample* when reading in the data.
            
            *north*: [ True | False ]
                Whether to rotate the image so that the North Celestial
                Pole is up. Note that this option requires Montage to be
                installed.
        
        Any additional arguments are passed on to matplotlib's Figure() class.
        For example, to set the figure size, use the figsize=(xsize,ysize)
        argument (where xsize and ysize are in inches). For more information
        on these additional arguments, see the *Optional keyword arguments*
        section in the documentation for Figure_
        
        .. _Figure: http://matplotlib.sourceforge.net/api/figure_api.html?#matplotlib.figure.Figure
        
        '''
        
        if not kwargs.has_key('figsize'):
            kwargs['figsize'] = (9,9)
        
        self._hdu,self._wcs = self._get_hdu(data,hdu,north)
        
        # Downsample if requested
        if downsample:
            naxis1_new = self._wcs.naxis1 - np.mod(self._wcs.naxis1,downsample)
            naxis2_new = self._wcs.naxis2 - np.mod(self._wcs.naxis2,downsample)
            self._hdu.data = self._hdu.data[0:naxis2_new,0:naxis1_new]
            self._hdu.data = image_util.resample(self._hdu.data,downsample)
            self._wcs.naxis1,self._wcs.naxis2 = naxis1_new,naxis2_new
        
        # Open the figure
        if figure:
            self._figure = figure
        else:
            self._figure = mpl.figure(**kwargs)
        
        if axesgrid:
            
            # Create first axis instance
            if subplot:
                self._ax1 = mpltk.HostAxes(self._figure,subplot,adjustable='datalim')
            else:
                self._ax1 = mpltk.SubplotHost(self._figure,1,1,1)
            
            self._ax1.toggle_axisline(False)
            
            self._figure.add_axes(self._ax1)
            
            # Create second axis instance
            self._ax2 = self._ax1.twin()
            self._ax2.set_frame_on(False)
            
            self._ax2.toggle_axisline(False)
        
        else:
            
            if subplot:
                print "WARNING: axes_grid toolkit is not installed, cannot specify subplot area"
            
            # Create first axis instance
            self._ax1 = self._figure.add_subplot(111)
            
            # Create second axis instance
            self._ax2 = self._ax1.figure.add_axes(self._ax1.get_position(True),frameon=False,aspect='equal')
        
        # Turn off autoscaling
        self._ax1.set_autoscale_on(False)
        self._ax2.set_autoscale_on(False)
        
        # Store WCS in axes
        self._ax1.apl_wcs = self._wcs
        self._ax2.apl_wcs = self._wcs
        
        # Set view to whole FITS file
        self._initialize_view()
        
        # Initialize ticks
        self._initialize_ticks()
        
        # Initialize grid
        self._initialize_grid()
        
        # Initialize labels
        self._initialize_labels()
        
        # Initialize layers list
        self._initialize_layers()
        
        # Find generating function for vmin/vmax
        self._auto_v = image_util.percentile_function(self._hdu.data)
        
        # Set image holder to be empty
        self.image = None
        
        # Set default theme
        self.set_theme(theme='pretty',refresh=False)
    
    def _get_hdu(self,data,hdu,north):
        
        if type(data) == str:
            
            filename = data
            
            # Check file exists
            if not os.path.exists(filename):
                raise Exception("File not found: "+filename)
            
            # Read in FITS file
            try:
                hdu = pyfits.open(filename)[hdu]
            except:
                raise Exception("An error occured while reading the FITS file")
        
        elif isinstance(data,pyfits.PrimaryHDU) or isinstance(data,pyfits.ImageHDU):
            
            hdu = data
        
        elif isinstance(data,pyfits.HDUList):
            
            hdu = data[hdu]
        
        else:
            
            raise Exception("data argument should either be a filename, or an HDU instance from pyfits.")
        
        # Reproject to face north if requested
        if north:
            hdu = montage.reproject_north(hdu)
        
        # Check header
        hdu.header = header.check(hdu.header)
        
        # Parse WCS info
        try:
            wcs = pywcs.WCS(hdu.header)
        except:
            raise Exception("An error occured while parsing the WCS information")
        
        return hdu,wcs
    
    def recenter(self,x,y,radius=None,width=None,height=None,refresh=True):
        '''
        Center the image on a given position and with a given radius
        
        Required Arguments:
            
            *x*: [ float ]
                Longitude of the position to center on (degrees)
            
            *y*: [ float ]
                Latitude of the position to center on (degrees)
            
        Optional Keyword Arguments:
            
            Either the radius or width/heigh arguments should be specified.
            
            *radius*: [ float ]
                Radius of the region to view (degrees). This produces a square plot.
                
            *width*: [ float ]
                Width of the region to view (degrees). This should be given in
                conjunction with the height argument.
            
            *height*: [ float ]
                Height of the region to view (degrees). This should be given in
                conjunction with the width argument.
            
            *refresh*: [ True | False ]
                Whether to refresh the display straight after setting the parameter.
                For non-interactive uses, this can be set to False.
        '''
        
        xpix,ypix = wcs_util.world2pix(self._wcs,x,y)
        
        degperpix = wcs_util.degperpix(self._wcs)
        
        if radius:
            dx_pix = radius / degperpix
            dy_pix = radius / degperpix
        elif width and height:
            dx_pix = width / degperpix / 2.
            dy_pix = height / degperpix / 2.
        else:
            raise Exception("Need to specify either radius= or width= and height= arguments")
            
        self._ax1.set_xlim(xpix-dx_pix,xpix+dx_pix)
        self._ax1.set_ylim(ypix-dy_pix,ypix+dy_pix)
        
        if refresh: self.refresh()
    
    def show_grayscale(self,vmin=None,vmid=None,vmax=None, \
                            pmin=0.25,pmax=99.75, \
                            stretch='linear',exponent=2,invert='default'):
        '''
        Show a grayscale image of the FITS file
        
        Optional Keyword Arguments:
            
            *vmin*: [ None | float ]
                Minimum pixel value to use for the grayscale. If set to None,
                the minimum pixel value is determined using pmin (default).
            
            *vmax*: [ None | float ]
                Maximum pixel value to use for the grayscale. If set to None,
                the maximum pixel value is determined using pmax (default).
            
            *pmin*: [ float ]
                Percentile value used to determine the minimum pixel value to
                use for the grayscale if vmin is set to None. The default
                value is 0.25%.
            
            *pmax*: [ float ]
                Percentile value used to determine the maximum pixel value to
                use for the grayscale if vmax is set to None. The default
                value is 99.75%.
            
            *stretch*: [ 'linear' | 'log' | 'sqrt' | 'arcsinh' | 'power' ]
                The stretch function to use
            
            *vmid*: [ None | float ]
                Mid-pixel value used for the log and arcsinh stretches. If
                set to None, this is set to a sensible value.
            
            *exponent*: [ float ]
                If stretch is set to 'power', this is the exponent to use
            
            *invert*: [ True | False ]
                Whether to invert the grayscale or not. The default is False,
                unless set_theme is used, in which case the default depends on
                the theme.
        '''
        
        if invert=='default':
            invert = self._get_invert_default()
        
        if invert:
            cmap = 'gist_yarg'
        else:
            cmap = 'gray'
        
        self.show_colorscale(vmin=vmin,vmid=vmid,vmax=vmax,stretch=stretch,exponent=exponent,cmap=cmap,pmin=pmin,pmax=pmax)
    
    def show_colorscale(self,vmin=None,vmid=None,vmax=None, \
                             pmin=0.25,pmax=99.75,
                             stretch='linear',exponent=2,cmap='default'):
        '''
        Show a colorscale image of the FITS file
        
        Optional Keyword Arguments:
            
            *vmin*: [ None | float ]
                Minimum pixel value to use for the colorscale. If set to None,
                the minimum pixel value is determined using pmin (default).
            
            *vmax*: [ None | float ]
                Maximum pixel value to use for the colorscale. If set to None,
                the maximum pixel value is determined using pmax (default).
            
            *pmin*: [ float ]
                Percentile value used to determine the minimum pixel value to
                use for the colorscale if vmin is set to None. The default
                value is 0.25%.
            
            *pmax*: [ float ]
                Percentile value used to determine the maximum pixel value to
                use for the colorscale if vmax is set to None. The default
                value is 99.75%.
            
            *stretch*: [ 'linear' | 'log' | 'sqrt' | 'arcsinh' | 'power' ]
                The stretch function to use
            
            *vmid*: [ None | float ]
                Mid-pixel value used for the log and arcsinh stretches. If
                set to None, this is set to a sensible value.
            
            *exponent*: [ float ]
                If stretch is set to 'power', this is the exponent to use
            
            *cmap*: [ string ]
                The name of the colormap to use
        '''
        
        if cmap=='default':
            cmap = self._get_colormap_default()
        
        min_auto = not m.isnumeric(vmin)
        mid_auto = not m.isnumeric(vmid)
        max_auto = not m.isnumeric(vmax)
        
        # The set of available functions
        cmap = mpl.cm.get_cmap(cmap,1000)
        
        vmin_auto,vmax_auto = self._auto_v(pmin),self._auto_v(pmax)
        
        if min_auto:
            print "Auto-setting vmin to %10.3e" % vmin_auto
            vmin = vmin_auto
        
        if max_auto:
            print "Auto-setting vmax to %10.3e" % vmax_auto
            vmax = vmax_auto
        
        if mid_auto:
            vmid = None
        else:
            vmid = (vmid - vmin) / (vmax - vmin)
        
        stretched_image = (self._hdu.data - vmin) / (vmax - vmin)
        
        if min_auto:
            vmin = -0.1
        else:
            vmin = 0.
        
        if vmax_auto:
            vmax = +1.1
        else:
            vmax = +1
        
        # Set stretch
        stretched_image = image_util.stretch(stretched_image,function=stretch,exponent=exponent,midpoint=vmid)
        
        if self.image:
            self.image.set_data(stretched_image)
            self.image.set_cmap(cmap=cmap)
            self.image.set_clim(vmin,vmax)
            self.image.origin='lower'
        else:
            self.image = self._ax1.imshow(stretched_image,cmap=cmap,vmin=vmin,vmax=vmax,interpolation='nearest',origin='lower',extent=self._extent)
        
        xmin,xmax = self._ax1.get_xbound()
        if xmin == 0.0: self._ax1.set_xlim(0.5,xmax)
        
        ymin,ymax = self._ax1.get_ybound()
        if ymin == 0.0: self._ax1.set_ylim(0.5,ymax)
        
        self.refresh()
    
    def show_rgb(self,filename,interpolation='nearest'):
        '''
        Show a 3-color image instead of the FITS file data
        
        Required Arguments:
            
            *filename*
                The 3-color image should have exactly the same dimensions as the FITS file, and
                will be shown with exactly the same projection.
        
        '''
        
        pretty_image = mpl.imread(filename)
        self.image = self._ax1.imshow(pretty_image,extent=self._extent,interpolation=interpolation,origin='upper')
        self.refresh()
    
    def show_contour(self,data,hdu=0,layer=None,levels=5,filled=False,cmap=None,colors=None,returnlevels=False,**kwargs):
        '''
        Overlay contours on the current plot
        
        Required Arguments:
            
            *data*: [ string | pyfits PrimaryHDU | pyfits ImageHDU ]
                Either the filename of the FITS file to open, or a pyfits
                PrimaryHDU or ImageHDU instance.
        
        Optional Keyword Arguments:
            
            *hdu*: [ integer ]
                By default, the image in the primary HDU is read in. If a
                different HDU is required, use this argument.
            
            *layer*: [ string ]
                The name of the contour layer. This is useful for giving
                custom names to layers (instead of contour_set_n) and for
                replacing existing layers.
            
            *levels*: [ int | list ]
                This can either be the number of contour levels to compute
                (if an integer is provided) or the actual list of contours
                to show (if a list of floats is provided)
            
            *filled*: [ True | False ]
                Whether to show filled or line contours
            
            *cmap*: [ string ]
                The colormap to use for the contours
            
            *colors*: [ string | tuple of strings ]
                If a single string is provided, all contour levels will be
                shown in this color. If a tuple of strings is provided,
                each contour will be colored according to the corresponding
                tuple element.
            
            *returnlevels*: [ True | False ]
                Whether to return the list of contours to the caller.
            
            Any additional keyword arguments will be passed on directly to
            matplotlib's contour or contourf methods. This includes for
            example the alpha, linewidths, and linestyles arguments which
            can be used to further control the appearance of the contours.
            
            For more information on these additional arguments, see the
            *Optional keyword arguments* sections in the documentation for
            contour_ and contourf_.
            
            .. _contour: http://matplotlib.sourceforge.net/api/axes_api.html?#matplotlib.axes.Axes.contour
            .. _contourf: http://matplotlib.sourceforge.net/api/axes_api.html?#matplotlib.axes.Axes.contourf`
        
        '''
        if layer:
            self.remove_layer(layer,raise_exception=False)
        
        if cmap:
            cmap = mpl.cm.get_cmap(cmap,1000)
        elif not colors:
            cmap = mpl.cm.get_cmap('jet',1000)
        
        hdu_contour,wcs_contour = self._get_hdu(data,hdu,False)
        
        image_contour = hdu_contour.data
        extent_contour = (0.5,wcs_contour.naxis1+0.5,0.5,wcs_contour.naxis2+0.5)
        
        if type(levels) == int:
            auto_levels = image_util.percentile_function(image_contour)
            vmin = auto_levels(0.25)
            vmax = auto_levels(99.75)
            levels = np.linspace(vmin,vmax,levels)
        
        self._name_empty_layers('user')
        
        if filled:
            self._ax1.contourf(image_contour,levels,extent=extent_contour,cmap=cmap,colors=colors,**kwargs)
        else:
            self._ax1.contour(image_contour,levels,extent=extent_contour,cmap=cmap,colors=colors,**kwargs)
        
        self._ax1 = contour_util.transform(self._ax1,wcs_contour,self._wcs)
        
        if layer:
            contour_set_name = layer
        else:
            self._contour_counter += 1
            contour_set_name = 'contour_set_'+str(self._contour_counter)
        
        self._name_empty_layers(contour_set_name)
        
        self.refresh()
        
        if returnlevels:
            return levels
    
    # This method plots markers. The input should be an Nx2 array with WCS coordinates
    # in degree format.
    
    def show_markers(self,xw,yw,layer=False,**kwargs):
        '''
        Overlay markers on the current plot.
        
        Required arguments:
            
            *xw*: [ list | numpy.ndarray ]
                The x postions of the markers (in world coordinates)
            
            *yw*: [ list | numpy.ndarray ]
                The y positions of the markers (in world coordinates)
        
        Optional Keyword Arguments:
            
            *layer*: [ string ]
                The name of the scatter layer. This is useful for giving
                custom names to layers (instead of scatter_set_n) and for
                replacing existing layers.
            
            Any additional keyword arguments will be passed on directly to
            matplotlib's scatter method. This includes for example the marker,
            alpha, edgecolor, and facecolor arguments which can be used to
            further control the appearance of the markers.
            
            For more information on these additional arguments, see the
            *Optional keyword arguments* sections in the documentation for
            scatter_.
            
            .. _scatter: http://matplotlib.sourceforge.net/api/axes_api.html?#matplotlib.axes.Axes.scatter
        
        '''
        
        if not kwargs.has_key('c'):
            kwargs.setdefault('edgecolor','red')
            kwargs.setdefault('facecolor','none')
        
        kwargs.setdefault('s',30)
        
        if layer:
            self.remove_layer(layer,raise_exception=False)
        
        self._name_empty_layers('user')
        
        xp,yp = wcs_util.world2pix(self._wcs,xw,yw)
        self._ax1.scatter(xp,yp,**kwargs)
        
        if layer:
            scatter_set_name = layer
        else:
            self._scatter_counter += 1
            scatter_set_name = 'scatter_set_'+str(self._scatter_counter)
        
        self._name_empty_layers(scatter_set_name)
        
        self.refresh()
    
    def refresh(self):
        self._figure.canvas.draw()
    
    def save(self,filename,dpi=None,transparent=False):
        '''
        Save the current figure to a file
        
        Required arguments:
            
            *filename*: [ string ]
                The name of the file to save the plot to. This can be
                for example a PS, EPS, PDF, PNG, JPEG, or SVG file.
        
        Optional Keyword Arguments:
            
            *dpi*: [ float ]
                The output resolution, in dots per inch. If the output file
                is a vector graphics format (such as PS, EPS, PDF or SVG) only
                the image itself will be rasterized. If the output is a PS or
                EPS file and no dpi is specified, the dpi is automatically
                calculated to match the resolution of the image. If this value is
                larger than 300, then dpi is set to 300.
            
            *transparent*: [ True | False ]
                Whether to preserve transparency
        
        '''
        
        if dpi == None and os.path.splitext(filename)[1] in ['.EPS','.eps','.ps','.PS','.Eps','.Ps']:
            width = self._ax1.get_position().width * self._figure.get_figwidth()
            interval = self._ax1.xaxis.get_view_interval()
            nx = interval[1] - interval[0]
            dpi = np.minimum( nx / width, 300.)
            print "Auto-setting resolution to ",dpi," dpi"
        self._figure.savefig(filename,dpi=dpi,transparent=transparent)
    
    def _initialize_view(self):
        
        self._ax1.xaxis.set_view_interval(+0.5,self._wcs.naxis1+0.5)
        self._ax1.yaxis.set_view_interval(+0.5,self._wcs.naxis2+0.5)
        self._ax2.xaxis.set_view_interval(+0.5,self._wcs.naxis1+0.5)
        self._ax2.yaxis.set_view_interval(+0.5,self._wcs.naxis2+0.5)
        
        # set the image extent to FITS pixel coordinates
        self._extent = (0.5,self._wcs.naxis1+0.5,0.5,self._wcs.naxis2+0.5)
    
    def _get_invert_default(self):
        return self._figure.apl_grayscale_invert_default
    
    def _get_colormap_default(self):
        return self._figure.apl_colorscale_cmap_default
    
    def set_theme(self,theme,refresh=True):
        '''
        Set the axes, ticks, grid, and image colors to a certain style (experimental)
        
        Required Arguments:
            
            *theme*: [ string ]
                The theme to use. At the moment, this can be 'pretty' (for
                viewing on-screen) and 'publication' (which makes the ticks
                and grid black, and displays the image in inverted grayscale)
        
        Optional Keyword Arguments:
            
            *refresh*: [ True | False ]
                Whether to refresh the display straight after setting the parameter.
                For non-interactive uses, this can be set to False.
        '''
        
        if theme=='pretty':
            self.set_frame_color('white',refresh=False)
            self.set_tick_color('white',refresh=False)
            self.set_tick_size(7,refresh=False)
            self._figure.apl_grayscale_invert_default = False
            self._figure.apl_colorscale_cmap_default  = 'jet'
            self.set_grid_color('white')
            self.set_grid_alpha(0.5)
            if self.image:
                self.image.set_cmap(cmap=mpl.cm.get_cmap('jet',1000))
        elif theme=='publication':
            self.set_frame_color('black',refresh=False)
            self.set_tick_color('black',refresh=False)
            self.set_tick_size(7,refresh=False)
            self._figure.apl_grayscale_invert_default = True
            self._figure.apl_colorscale_cmap_default  = 'gist_heat'
            self.set_grid_color('black')
            self.set_grid_alpha(1.0)
            self.image.set_cmap(cmap='jet')
            if self.image:
                self.image.set_cmap(cmap=mpl.cm.get_cmap('gist_yarg',1000))
        
        if refresh: self.refresh()
    
    def set_frame_color(self,color,refresh=True):
        '''
        Set color of the frame
        
        Required arguments:
            
            *color*:
                The color to use for the frame.
        
        Optional Keyword Arguments:
            
            *refresh*: [ True | False ]
                Whether to refresh the display straight after setting the parameter.
                For non-interactive uses, this can be set to False.
        '''
        
        # The matplotlib API changed in 0.98.6
        try:
            self._ax1.frame.set_edgecolor(color)
        except AttributeError:
            for key in self._ax1.spines:
                self._ax1.spines[key].set_edgecolor(color)
        
        if refresh: self.refresh()