#!/usr/bin/python
# Filename: atmos_basic.py
#
# Code by Martin Jucker, distributed under an MIT License
# Any publication benefitting from this piece of code should cite
# Jucker, M 2014. Scientific Visualisation of Atmospheric Data with ParaView.
# Journal of Open Research Software 2(1):e4, DOI: http://dx.doi.org/10.5334/jors.al
#
# Python interface for ParaView (www.paraview.org). Reads netCDF file on a latitude - longitude and, if desired, pressure or height coordinates grid, including time evolution (if present). netCDF file needs to correspond to Climate and Forecast (FC) conventions (https://en.wikipedia.org/wiki/Climate_and_Forecast_Metadata_Conventions).
# Also Provides functions to modify Cartesian coordinates and wind components.

##### needed modules: paraview.simple, math #########################
from paraview.simple import *
from math import pi,log10

# some global constants
strPi = str(pi)[0:7]

##### define auxiliary functions ##################################
def CorrectZCoord(src=GetActiveSource()):
    """Make sure Z coordinate points in positive direction. This is redundant for version >= 1.1

    Adds a Calculator filter to the pipeline, which takes the absolute value of coordsZ:
    src -- filter in pipeline to attach Calculator
    """
    calc=Calculator(src)
    calc.Function = 'iHat*coordsX + jHat*coordsY + kHat*abs(coordsZ)'
    calc.CoordinateResults = 1
    return calc

# define logarithmic coordinate conversion
def ConvertLogCoordString(pString, basis=1e3):
    """Logarithmic coordinate conversion in string form for Calculator filter.

    Output is the string to be used inside the Calculator filter:
    pString -- the coordinate to convert
    basis   -- basis (surface) pressure to normalize
    """
    expression = 'abs(log10(abs(' + pString + ')/' + str(basis) + '))'
    return expression
	
def ConvertPressureString(pString, ratio=1.0, basis=1e3):
    """ConvertPressureString() is deprecated. Please use ConvertLogCoordString()"""
    import warnings
    warnings.warn("ConvertPressureString() is deprecated, please use ConvertLogCoordString() in the future", DeprecationWarning)
    expression = ConvertLogCoordString(pString, basis=basis)
    expression = expression+'*'+str(ratio)
    return expression

# do the coordinate conversion inside a Calculator
def Cart2Log(src=GetActiveSource(), ratios=[1,1,1], logCoords=[2], basis=[1e3]):
    """Convert between logarithmic and linear coordinates. Also applies aspect ratio correction.

    Adds a Calculator filter to the pipeline
    src       -- filter in pipeline to attach to
    ratios    -- multiplicative factor for coordinates - must be same length as # of dimensions
    logCoords -- indices (0 based) of coordinates to be converted
    basis     -- basis to normalize argument to logarithm (ie defines origin) - must be length 1 or same as logCoords
    """
    nVec=['iHat*','jHat*','kHat*']
    coords=['coordsX','coordsY','coordsZ']
    cFun=coords[:]
    pFun=''
    for pp in range(len(logCoords)):
        ci = logCoords[pp]
        if len(basis) == 1:
            bas = basis[0]
        else:
            bas = basis[pp]
        cFun[ci] = ConvertLogCoordString(coords[ci], bas)
    for ii in range(len(ratios)):
        if ratios[ii] != 1.0:
            pFun += nVec[ii]+cFun[ii] + '*'+str(ratios[ii]) + ' + '
        else:
            pFun += nVec[ii]+cFun[ii] + ' + '
    calc=Calculator(src)
    calc.Function = pFun[:-3]
    calc.CoordinateResults = 1
    return calc
	

def Pressure2Cart(src=GetActiveSource(), ratio=1.0, basis=1e3):
	"""Pressure2Cart() is deprecated. Please use Cart2Log()."""
	import warnings
	warnings.warn("Pressure2Cart() is deprecated. Please use Cart2Log().",DeprecationWarning)
	calc=Cart2Log(src,[1,1,ratio],basis=[basis])
	return calc

def Cart2Spherical(radius=1.0, src=GetActiveSource()):
    """Convert Cartesian to spherical coordinates. 

    Assumes X coordinate is longitude, Y coordinate latitude, Z coordinate vertical.
    Adds Calculator filter to the pipeline.
    radius -- radius of the sphere, where coordZ = basis
    src    -- filter in pipeline to attach to
    """
    calc=Calculator(src)
    strRad = str(radius)
    try:
        calc.Function = 'iHat*('+strRad+'+coordsZ)*cos(coordsY*'+strPi+'/180)*cos(coordsX*'+strPi+'/180) + jHat*('+strRad+'+coordsZ)*cos(coordsY*'+strPi+'/180)*sin(coordsX*'+strPi+'/180) + kHat*('+strRad+'+coordsZ)*sin(coordsY*'+strPi+'/180)'
    except:
        calc.Function = 'iHat*'+strRad+'*cos(coordsY*'+strPi+'/180)*cos(coordsX*'+strPi+'/180) + jHat*'+strRad+'*cos(coordsY*'+strPi+'/180)*sin(coordsX*'+strPi+'/180) + kHat*'+strRad+'*sin(coordsY*'+strPi+'/180)'
    calc.CoordinateResults = 1
    RenameSource('Cart2Spherical',calc)
    return calc

# apply aspect ratios to grid. This might already be done in Cart2Log
def GridAspectRatio(ratios, src=GetActiveSource()):
    """Adjust aspect ratio of Cartesian grid: multiplies ratios x coordinates.

    Adds Calculator filter to the pipeline.
    ratios -- 2- or 3-vector with multiplicative factors for each spatial coordinate
    """
    calc=Calculator(src)
    try:
        calc.Function = 'iHat*'+str(ratios[0])+'*coordsX + jHat*'+str(ratios[1])+'*coordsY + kHat*'+str(ratios[2])+'*coordsZ'
    except:
        calc.Function = 'iHat*'+str(ratios[0])+'*coordsX + jHat*'+str(ratios[1])+'*coordsY'
    calc.CoordinateResults = 1
    return calc

# transform coordinates: logarithmic, aspect ratio
def TransformCoords(src=GetActiveSource(), aspectRatios=[1,1,1], logCoords=[2], basis=1e3):
    """Transform the coordinates depending on whether or not there are logarithmic coordinates"""
    if len(logCoords)>0 :
        transCoor = Cart2Log(src=src,ratios=aspectRatios,logCoords=logCoords,basis=basis)
    else:
        transCoor = GridAspectRatio(ratios=aspectRatios, src=src)
	return transCoor

#
def MakeSelectable(src=GetActiveSource()):
    """Make filter selectable in pipeline browser, but don't show it."""
    rep=Show(src)
    rep.Visibility=0


######### read in data, redefine pressure coordinates and change aspect ratio ###############

def LoadData( fileName, ncDims=['lon','lat','pfull'], aspectRatios=[1,1,1], logCoords=[2], basis=[1e3] ):
    """Load netCDF file, convert coordinates into useful aspect ratio.

    Adds file output_nc, and Calculator LogP or Calculator AspRat to the pipeline
    
    INPUTS:
        fileName      -- full path and file name of data to be read
        ncDims        -- names of the dimensions within the netCDF file. Time should be excluded. Ordering [x,y,z]
        aspectRatios  -- how to scale coordinates [xscale,yscale,zscale]. Z coordinate is scaled after applying log10 for logarithmic axes
        logCoords     -- index/indices of dimension(s) to be logarithmic
        basis         -- basis to normalize argument to logarithm (ie defines origin). List of same length as logCoords
    OUTPUTS:
        output_nc     -- netCDF reader object with the file data as read
        transCoor     -- Calculator filter corresponding to the transformed coordinates
    """ 
    # outputDimensions must be in same sequence as in netCDF file, except time (e.g. ['pfull','lat','lon'] ). This is usually the "wrong" way round
    outputDimensions = ncDims[::-1]
    output_nc = NetCDFReader( FileName=[fileName] )

    if len(outputDimensions)>0 :
        outDims = '('+ outputDimensions[0]
        for dim in range(1,len(outputDimensions)):
            outDims = outDims + ', ' + outputDimensions[dim]
        outDims += ')'
        output_nc.Dimensions = outDims
    
    output_nc.SphericalCoordinates = 0
    output_nc.OutputType = 'Unstructured'
    output_nc.ReplaceFillValueWithNan = 0
    MakeSelectable()
    RenameSource(fileName,output_nc)
    
    transCoor = TransformCoords(src=output_nc,aspectRatios=aspectRatios,logCoords=logCoords,basis=basis)
    MakeSelectable()
	
    if len(logCoords)>0 :
        RenameSource('LogCoor',transCoor)
    else:
<<<<<<< HEAD
        AspRat = GridAspectRatio(aspectRatios, output_nc)
        MakeSelectable(AspRat)
        return output_nc,AspRat

#return output_nc,CorrZ,Coor,AspRat
=======
        RenameSource('TransCoor',transCoor)
    return output_nc,transCoor
>>>>>>> FETCH_HEAD

def loadData( fileName, ncDims=['lon','lat','pfull'], aspectRatios=[1,1,1], basis=1e3 ):
    """This is deprecated, please use LoadData()"""
    import warnings
    (output_nc,CorrZ,Coor,AspRat)=LoadData( fileName, ncDims=['lon','lat','pfull'], aspectRatios=[1,1,1], logCoords=[2], basis=1e3 )
    warnings.warn("loadData() is deprecated, please use LoadData() in the future", DeprecationWarning)
    return output_nc,CorrZ,Coor,AspRat

######## convert 2D into 3D data using a variable as third dimension ##############

def Make3D( expandVar, expandDir='z', aspectRatios=[1,1,1], logCoords=[], basis=1e3, src=GetActiveSource() ):
    """Expand any 2D dataset into 3D with the values of a field.
        
        Make3D takes a 2D dataset, and adds a third dimension corresponding to a data field.
        
        INPUTS:
            expandVar    -- name of the variable to use as third dimension
            expandDir    -- direction in which to expand {'x','y','z'}
            aspectRatios -- how to scale coordinates [xscale,yscale,zscale]. Z coordinate is scaled after applying log10 for logarithmic axes
            logCoords    -- index/indices of dimension(s) to be logarithmic
            basis        -- basis to normalize argument to logarithm (ie defines origin). List of same length as logCoords
            src          -- source fiter to attach to
        OUPUTS:
            trans3d      -- a Calculator filter with the transformed 3D field
    """
	make3d = Calculator(src)
	if expandDir.lower() == 'x':
		make3d.Function = 'iHat*'+expandVar+' + jHat*coordsY + kHat*coordsZ)'
	elif expandDir.lower() == 'y':
		make3d.Function = 'iHat*coordsX + jHat*'+expandVar+' + kHat*coordsZ)'
	elif expandDir.lower() == 'z':
		make3d.Function = 'iHat*coordsX + jHat*coordsY + kHat*'+expandVar
	else:
		raise Exception("Make3D: expandDir has to be one of x,y,z, but is "+expandDir)
	make3d.CoordinateResults = 1
	
	trans3d = TransformCoords(src=make3d,aspectRatios=aspectRatios,logCoords=logCoords,basis=basis)
	
	return trans3d

######## some other usefull tools #################################################

# transform winds from SI to plot units
def CartWind2Atmos(src=GetActiveSource(), zonalComponentName='ucomp', meridionalComponentName='vcomp', secondsPerTimeStep=86400, verticalComponentName='none', ratios=[1,1,1]):
    """Convert wind components from m/s to lat/timeStep, lon/timeStep, z/timeStep, and store it as vector W. 

    Works with both pressure and height velocity, as long as vertAsp = [initial vertical range]/[present vertical range] is given. 
    INPUTS:
        src                     -- filter in pipeline to attach to
        zonalComponentName      -- name of zonal wind component in pipeline
        meridionalComponentName -- name of meridional wind component in pipeline
        secondsPerTimeStep      -- duration of time step in seconds: 86400 for daily
        verticalComponentName   -- name of vertical component, or 'none'
        ratios                  -- Corrections to actually plotted axes
    OUTPUTS:
        Adds two Calculators to the pipeline:
        W     -- wind vector calculation
        normW -- magnitude of wind vector
        Adds two slices to the pipeline to remove division by zero close to poles:
        clipS -- remove south pole
        clipN -- remove north pole
    """
    W=Calculator(src)
    if verticalComponentName != 'none' :
        W.Function = '(' + \
        'iHat*'+zonalComponentName+'/(6.28*6.4e6*cos(coordsY/'+str(ratios[1])+'*'+strPi+'/180))*360 +' + \
        'jHat*'+meridionalComponentName+'/('+strPi+'*6.4e6)*180 +' + \
        'kHat*'+verticalComponentName+'/'+vertAsp + \
        ')*'+str(secondsPerTimeStep) 
    else:
        W.Function =  '(' + \
        'iHat*'+zonalComponentName+'/(6.28*6.4e6*cos(coordsY/'+str(ratios[1])+'*'+strPi+'/180))*360 +' + \
        'jHat*'+meridionalComponentName+'/('+strPi+'*6.4e6)*180' + \
        ')*'+str(secondsPerTimeStep)  
    W.ResultArrayName = 'W'
    RenameSource('CartWind2Atmos',W)
    MakeSelectable(W)
    # add the magnitdue of the wind vector, i.e wind strength. nice to have for color, threshold, glyph filters later on
    norm = Calculator(W)
    norm.Function = 'mag(W)'
    norm.ResultArrayName = 'normW'
    RenameSource('normW',norm)
    MakeSelectable(norm)
    # conversion invloves a division by zero over the poles. to avoid large numbers, cut away anything higher than 80 degrees
    clipS = Clip(norm)
    clipS.ClipType = 'Plane'
    clipS.ClipType.Normal = [0.0, 1.0, 0.0]
    clipS.ClipType.Origin  = [0.0, -80.0*ratios[1], 0.0]
    RenameSource('clipS',clipS)
    MakeSelectable(clipS)
    clipN = Clip(clipS)
    clipN.ClipType = 'Plane'
    clipN.ClipType.Normal = [0.0,-1.0, 0.0]
    clipN.ClipType.Origin  = [0.0, 80.0*ratios[1], 0.0]
    RenameSource('clipN',clipN)
    MakeSelectable(clipN)
return W,norm,clipS,clipN

# extract the boundaries of a filter
def ExtractBounds(src=GetActiveSource()):
    """Return the axis extremities (bounds) of any source filter
        
        Inputs:
        src    - filter to extract bounds of
        Outputs:
        bounds - list of (xmin,xmax [,ymin,ymax [,zmin,zmax]])"""
    bounds = src.GetDataInformation().GetBounds()
    return bounds

## working with a spherical geometry: conversion functions
def Sphere2xyz(coords, lam, phi):
    """Compute (x,y,z) from coords=(r,lam,phi) or r,lam,phi, where lam=0 at the Equator, -90 <= lam <= 90 (latitude),
        and phi=0 along x-axis, 0 <= phi <= 360 (longitude)
        Also computes the normal along the radial direction (useful for placing and orienting the camera).
        
        INPUTS:
            coords - list of (radius,lambda,phi) or radius
            lam    - lambda (declination, latitude) if coords is radius
            phi    - phi (azimuth, longitude) if coords is radius
        OUTPUTS:
            xyzPos - list of corresponding (x,y,z)
            normal - list of (xn,yn,zn) along radial direction
    """
    from numpy import pi,sin,cos,array
    if len(coords) == 3:
        rr=coords[0];lam=coords[1];phi=coords[2]
    elif len(coords) == 1:
        rr=coords
    else:
        raise Exception("Sphere2xyz: coords has to be a list of length 3 (r,lambda,phi), or a scalar (radius)")
    xyzPos = [rr*cos(lam*pi/180)*cos(phi*pi/180),rr*cos(lam*pi/180)*sin(phi*pi/180),rr*sin(lam*pi/180)]
    rr=rr+1
    p1     = [rr*cos(lam*pi/180)*cos(phi*pi/180),rr*cos(lam*pi/180)*sin(phi*pi/180),rr*sin(lam*pi/180)]
    normal = list(array(p1) - array(xyzPos))
    return xyzPos,normal
#
def xyz2Sphere(coords, y, z):
    """Compute (r,lam,phi) from coords=(x,y,z) or x,y,z, where lam=0 at the Equator, -90 <= lam <= 90 (latitude),
        and phi=0 along x-axis, 0 <= phi <= 360 (longitude)
        
        INPUTS:
            coords - list of (x,y,z) or x
            y      - y coordinate if coords is x
            z      - z coordinate if coords is x
        OUTPUTS:
            sphPos - list of corresponding (r,lam,phi)
    """
    from numpy import sqrt,pi,sin,cos,arcsin,arctan
    if len(coords == 3):
        x=coords[0];y=coords[1];z=coords[2]
    elif len(coords) == 1:
        x = coords
    else:
        raise Exception("xyz2Sphere: coords has to be a list of length 3 (x,y,z), or a scalar (x)")
    r   = sqrt(x*x + y*y + z*z)
    if x > 0:
        phi = arctan(y/x)
    elif x < 0:
        phi = pi + arctan(y/x)
    elif x == 0 and y > 0:
        phi = 0.5*pi
    elif x == 0 and y < 0:
        phi = 1.5*pi
    lam = arcsin(z/r)
    return (r,lam*180/pi,phi*180/pi)

## some simple helper functions
#
def DeleteAll():
    """Delete all objects in the pipeline browser."""
    for src in GetSources().values():
        Delete(src)
#
def HideAll():
    """Make all objects in pipeline browser invisible."""
    for src in GetSources().values():
    	Hide(src)
#
def ShowAll():
    """Make all objects in pipeline browser visible."""
    for src in GetSources().values():
        Show(src)
