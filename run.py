from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import sys
from argparse import ArgumentParser
import logging
import shutil

import os
import numpy as np
from shapely.geometry import shape, box, Polygon, Point, MultiPolygon, LineString
from shapely import wkt
from shapely.ops import split
import geopandas
import math
import cv2

from glob import glob

import cytomine
from cytomine import Cytomine, CytomineJob
from cytomine.models import Property, Annotation, AnnotationTerm, AnnotationCollection, Job, JobData, TermCollection, ImageInstanceCollection, ImageInstance


__author__ = "WSH Munirah W Ahmad <wshmunirah@gmail.com>"
__version__ = "0.0.2"
# Date created: 5 Oct 2023


def run(cyto_job, parameters):
    logging.info("----- Delete White Patches v%s -----", __version__)
    logging.info("Entering run(cyto_job=%s, parameters=%s)", cyto_job, parameters)

    job = cyto_job.job
    project = cyto_job.project
    id_user = parameters.cytomine_id_user

    job.update(status=Job.RUNNING, progress=10, statusComment="Initialization...")

    terms = TermCollection().fetch_with_filter("project", parameters.cytomine_id_project) 
    job.update(status=Job.RUNNING, progress=20, statusComment="Terms collected...")
    
    images = ImageInstanceCollection().fetch_with_filter("project", project.id)    
    list_imgs = []
    if parameters.cytomine_id_images == 'all':
        for image in images:
            list_imgs.append(int(image.id))
    else:
        list_imgs = [int(id_img) for id_img in parameters.cytomine_id_images.split(',')]
        print('Images: ', list_imgs)    
    job.update(status=Job.RUNNING, progress=30, statusComment="Images gathered...")
         
    id_project = parameters.cytomine_id_project
    id_user = parameters.cytomine_id_user
    id_term = parameters.cytomine_id_term
    th_remove=parameters.th_remove # percentage of pixels having white/light area to be removed                
    print("Percentage of pixels having white/light area to be removed :", th_remove)
    hist_bins=parameters.hist_bins
    
    working_path = os.path.join("tmp", str(job.id))
    
    if not os.path.exists(working_path):
        logging.info("Creating working directory: %s", working_path)
        os.makedirs(working_path)
    try:

        for id_image in list_imgs:
            imageinfo=ImageInstance(id=id_image,project=id_project)
            imageinfo.fetch()
            calibration_factor=imageinfo.resolution
            print('Parameters (id_project, id_image, id_term):',id_project, id_image, id_term)

            roi_annotations = AnnotationCollection()
            roi_annotations.project = id_project
            roi_annotations.image = id_image
            roi_annotations.term = id_term
            roi_annotations.showWKT = True
            roi_annotations.showMeta = True
            roi_annotations.showGIS = True
            roi_annotations.showTerm = True
            roi_annotations.includeAlgo=True
            if id_user:
                roi_annotations.user=id_user
            roi_annotations.fetch()
            
            # annotation_params = {
            #     "term": id_term,
            #     "project": id_project,
            #     "image": id_image,
            #     "showWKT": True         
            # }                
            
            # roi_user_annotations = AnnotationCollection(**annotation_params).fetch()
            # roi_algo_annotations = AnnotationCollection(**annotation_params, includeAlgo=True).fetch()
            # roi_annotations = roi_user_annotations + roi_algo_annotations
            print(roi_annotations)

            job.update(status=Job.RUNNING, progress=40, statusComment="Processing patches...")
            print("----------------------------Patches Annotations------------------------------")
            for i, roi in enumerate(roi_annotations):
                #Get Cytomine ROI coordinates for remapping to whole-slide
                #Cytomine cartesian coordinate system, (0,0) is bottom left corner
                
                roi_geometry = wkt.loads(roi.location)
                #Dump ROI image into local PNG file
                roi_path=os.path.join(working_path,str(roi_annotations.project)+'/'+str(roi_annotations.image)+'/')
                roi_png_filename=os.path.join(roi_path+str(roi.id)+'.png')
                roi.dump(dest_pattern=roi_png_filename)                    
                
                # check white patches
                J = cv2.imread(roi_png_filename,0) #read image and convert to grayscale    
                [r, c]=J.shape
                totalpixels=r*c
                white_patch_th = math.floor(totalpixels * th_remove) # white pixels threshold value
                hist,bins = np.histogram(J.ravel(),hist_bins,[0,256])
                
                if hist[hist_bins-1] > white_patch_th: # check the last bin, if exceeds white pixels threshold value, delete patch
                    print("White patch deleted: ", hist[hist_bins-1])
                    roi.delete() #delete splitpoly annotation to avoid double annotations, we want to keep only the classified annotations
                              
    finally:
        job.update(progress=100, statusComment="Run complete.")
        shutil.rmtree(working_path, ignore_errors=True)
        logging.debug("Leaving run()")
        
if __name__ == "__main__":
    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:
        run(cyto_job, cyto_job.parameters)
