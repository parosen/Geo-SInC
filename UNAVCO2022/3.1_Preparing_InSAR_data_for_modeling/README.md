# Preparing InSAR data for modeling

2022 InSAR Processing and Time-Series Analysis for Geophysical Applications: ISCE, ARIA-Tools, and MintPy

Instructors: Heresh Fattahi, Eric Fielding, Gareth Funning, Alex Lewandowski, Franz Meyer, Paul Rosen, Simran Sangha, Forrest William, Zhang Yunjun

TA’s: Niloufar Abolfathian, Becca Bussard, Brett Buzzanga, Emre Havazali

ISCE Version: v2.6

MintPy Version: v1.4.0

InSAR processing is only the starting point for a geophysical analysis of surface deformation. In order to use our unwrapped interferograms to constrain geophysical models, we need to consider a couple of things: the number of datapoints and the satellite line-of-sight vector. 

## Downsampling InSAR data with a quadtree decomposition

Using interferograms at full resolution could be considered overkill - the data are highly spatially correlated, and we do not need all of the pixels in an interferogram to represent the key information that it contains. Another consideration is that computation time in modeling scales with the number of data points you are trying to model, so there is a penalty for trying to model more data points than you need to.

We include two notebooks: quadtree_decomposition_kite and process_quadtree_output that use the <i>kite</i> tool in the <i>pyrocko</i> suite to downsample an interferogram using a quadtree decomposition, retaining the most important information and reducing the number of data points to hundreds (from millions!) Also, importantly, <i>kite</i> outputs line-of-sight information for each data point, which is necessary for modeling, as we shall see...

## Projecting modeled surface displacements into InSAR line-of-sight

InSAR measures displacement in the satellite line-of-sight direction, which we define as a 3-component unit vector. We measure movement towards or away from the satellite in this direction. Often this can result in some unusual-looking deformation patterns, as each component of surface displacement contributes to an interferogram differently.

To see how this works in practice, we include notebooks that calculate the expected displacement fields for the fault slip that occurs in an earthquake, and then project them into line-of-sight (okada_los_components and okada_ascending_descending). The model we use is for a rectangular dislocation in an elastic half space (Okada, 1985), which is a fast-to-compute model that is commonly used in geophysics to represent fault slip in earthquakes.

## Simple earthquake modeling using Okapy

Included are some notebooks that use the Okada rectangular dislocation code to make simple inverse models of the earthquake source using downsampled InSAR data (the output of the notebooks mentioned above). In one case (okapy_forward_model) we do this entirely manually, modifying the fault parameters by hand. In another (okapy_optimization), we use an optimization algorithm to automate the process. Both notebooks make use of Okapy, a Python-based realization of the Okada model.

Okapy (and its cousin Slippy) is under development at <a href="https://github.com/geniusinaction/okapy">Gareth Funning's GitHub repository</a>, which is where any future updates to the codes will be posted.

## Dependencies

* numpy
* scipy
* matplotlib
* pyrocko
* pyrocko/kite
* okada_wrappper
