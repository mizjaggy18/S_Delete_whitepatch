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

from shapely.wkt import loads as wkt_loads
from glob import glob

import cytomine
from cytomine import Cytomine, CytomineJob
from cytomine.models import Property, Annotation, AnnotationTerm, AnnotationCollection, Job, JobData, TermCollection, ImageInstanceCollection, ImageInstance


__author__ = "WSH Munirah W Ahmad <wshmunirah@gmail.com>"
__version__ = "0.0.2"
# Date created: 5 Oct 2023
# Function to check if ROI contains white patches
def contains_white_patches(image, hist_bins, th_remove):
    total_pixels = image.size
    hist, _ = np.histogram(image.ravel(), hist_bins, [0, 256])
    white_patch_th = math.floor(total_pixels * th_remove)
    return hist[hist_bins-1] > white_patch_th


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
    resize_ratio=parameters.resize_ratio
    
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

            if id_user:
                annotation_params = {
                    "term": id_term,
                    "project": id_project,
                    "user": id_user,
                    "image": id_image,
                    "showWKT": True         
                } 
            else:
                annotation_params = {
                    "term": id_term,
                    "project": id_project,
                    "image": id_image,
                    "showWKT": True         
                }
            
            roi_user_annotations = AnnotationCollection(**annotation_params).fetch()
            roi_algo_annotations = AnnotationCollection(**annotation_params, includeAlgo=True).fetch()
            roi_annotations = roi_user_annotations + roi_algo_annotations
            print(roi_annotations)

            job.update(status=Job.RUNNING, progress=40, statusComment="Processing patches...")
            print("----------------------------Patches Annotations------------------------------")            
            
            for i, roi in enumerate(roi_annotations):
                roi_geometry = wkt_loads(roi.location)
                roi_path = os.path.join(working_path, str(roi.project), str(roi.image))
                roi_png_filename = os.path.join(roi_path, str(roi.id) + '.png')
                roi.dump(dest_pattern=roi_png_filename)
                image = cv2.imread(roi_png_filename, 0)                
                width = int(image.shape[1] * resize_ratio / 100)
                height = int(image.shape[0] * resize_ratio / 100)
                dim = (width, height)                  
                # resize image
                image = cv2.resize(image, dim, interpolation = cv2.INTER_AREA)   
                # Check for white patches
                if contains_white_patches(image, hist_bins, th_remove):
                    print("White patch deleted")
                    roi.delete()  # Delete ROI if it contains white patches
                    
                              
    finally:
        job.update(progress=100, statusComment="Run complete.")
        shutil.rmtree(working_path, ignore_errors=True)
        logging.debug("Leaving run()")
        
if __name__ == "__main__":
    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:
        run(cyto_job, cyto_job.parameters)
