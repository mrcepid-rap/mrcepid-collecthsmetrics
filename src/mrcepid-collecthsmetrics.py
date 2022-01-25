#!/usr/bin/env python
# mrcepid-collecthsmetrics 0.0.1
# Generated by dx-app-wizard.
#
# Author: Eugene Gardner (eugene.gardner at mrc.epid.cam.ac.uk)
#
# DNAnexus Python Bindings (dxpy) documentation:
#   http://autodoc.dnanexus.com/bindings/python/current/

import dxpy
import subprocess
import gzip
import shutil
import csv
import os
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor


# This function runs a command on an instance
def run_cmd(cmd):

    # Standard python calling external commands protocol
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()

    # If the command doesn't work, print the error stream and close the AWS instance out with 'dxpy.AppError'
    if proc.returncode != 0:
        print("The following cmd failed:")
        print(cmd)
        print("STDERROR follows\n")
        print(stderr.decode('utf-8'))
        raise dxpy.AppError("Failed to run properly...")


# This function takes a DXFile object and returns the associated cram index as a DXFile object
# One issue is this might brake if UKBB ever switches away from .crai indicies
def get_cram_index(dx_cram):

    cram_folder = dx_cram.describe()['folder']
    cram_name = dx_cram.describe()['name']

    # This uses dxpy to search for the crai index associated with the cram file. I worry that this is way too hardcoded
    # and could easily break given changes to the underlying project/directory structure
    found_files = list(dxpy.find_data_objects(project = "project-G6F3238JvzZpKfB7FbbYpX92",
                                folder = cram_folder + "/",
                                name = cram_name + ".crai",
                                classname = "file"))
    if (len(found_files) == 1):
        index_file = found_files[0]['id']
        return dxpy.DXFile(index_file)
    else:
        raise dxpy.AppError('Incorrect number of index files (' + str(len(found_files)) + ') found.')


# This is just to compartmentalise the collection of all the resources I need for this task and
# get them into the right place
def ingest_resources(intervals):

    # Here we are downloading & unpacking resource files that are required for the annotation engine, they are:
    # 1. Human reference files
    reference_file = dxpy.DXFile(
        'file-Fx2x270Jx0j17zkb3kbBf6q2')  ## This is the location of the GRCh38 reference file on AWS London
    reference_index = dxpy.DXFile(
        'file-Fx2x21QJ06f47gV73kZPjkQQ')  ## This is the location of the GRCh38 reference index file on AWS London

    # Actually download the reference files to the instance:
    dxpy.download_dxfile(reference_file.get_id(), "reference.fasta.gz")
    dxpy.download_dxfile(reference_index.get_id(), "reference.fasta.fai")

    # Unzip reference file (Picard fails with gzipped .fa...?):
    cmd = "gunzip reference.fasta.gz"
    run_cmd(cmd)

    # Get the individual interval files
    interval_files = {}
    for interval_file in intervals:

        # This is similar to above where we are just downloading an interval file based on provided by dx file hash
        interval_file = dxpy.DXFile(interval_file)

        # This is a property set by Eugene when uploading the interval file to the DNANexus platform. See README for
        # more details
        interval_type = interval_file.get_properties()['interval_type']

        # And then download the file with that name and append to our dict of interval files:
        interval_path = interval_type + ".interval_list"
        dxpy.download_dxfile(interval_file.get_id(), interval_path)
        interval_files[interval_type] = interval_path

    return interval_files


# This is a helper function that will run individual threads (essentially just holds a future)
def process_cram(cram: str, interval_files: dict) -> dict:

    # This sets a dxpy file handle for the cram file that we want to
    cram = dxpy.DXFile(cram.rstrip())
    # Use the function get_cram_index() to find the associated cram index
    index = get_cram_index(cram)

    # Actually download cram file and index to the instance
    sample_id = cram.get_properties()['eid']

    print("Processing sample " + sample_id + "...\n")

    dxpy.download_dxfile(cram.get_id(), sample_id + ".cram")
    dxpy.download_dxfile(index.get_id(), sample_id + ".cram.crai")

    # Instantiate a dictionary to hold coverage values to allow easy printing to final file
    # To name the dict, pull sample ID from a dict of properties attached to any dxpy file handle
    # This is used to easily name output
    cov_values = {"sample": sample_id}

    # Now iterate through each provided interval file (in intervals) and provide it as input to picard to calculate coverage
    for interval_type, interval_file in interval_files.items():

        # Set a reasonable output file based on sample id and interval_type
        output_file = 'sample_%s.%s.txt' % (sample_id, interval_type)

        # Run picard itself using the run_cmd() function
        # Picard is stored as a "resource" and included with the app when building on DNANexus. See README for more details
        print("Performing coverage calculation on sample " + sample_id + " for interval: " + interval_type)
        cmd = "java -Xmx4000M -Xms4000M -XX:+UseSerialGC -jar /usr/bin/picard.jar CollectHsMetrics " \
              "-VALIDATION_STRINGENCY LENIENT " \
              "-I " + sample_id + ".cram " \
              "-BAIT_INTERVALS " + interval_file + " " \
              "-TARGET_INTERVALS " + interval_file + " " \
              "-O " + output_file + " " \
              "-R reference.fasta " \
              "-VERBOSITY ERROR"
        run_cmd(cmd)

        # Now read in the resulting csv file and pull the field we care about: "MEAN_TARGET_COVERAGE"
        # This feels slightly dangerous as I am assuming Picard always stores this information on lines 7 & 8...
        for i in csv.DictReader(open(output_file).readlines()[6:8], delimiter="\t"):
            cov_values[interval_type] = i['MEAN_TARGET_COVERAGE']

    cmd = "rm " + sample_id + ".cram"
    run_cmd(cmd)
    print("Finished processing sample " + sample_id + "...\n")

    return cov_values


@dxpy.entry_point('main')
def main(cram_list, intervals, output_file):

    # Get threads available to this instance
    threads = os.cpu_count()
    print('Number of threads available: %i' % threads)

    # This function just grabs resources necessary to run this code
    interval_files = ingest_resources(intervals)

    # Build a thread worker that contains as many threads, divided by 4 that have been requested
    # Loop through each VCF and do CADD annotation
    cram_list = dxpy.DXFile(cram_list)
    dxpy.download_dxfile(cram_list.get_id(), "cram_list.txt") # Actually download the file
    input_cram_reader = open("cram_list.txt", 'r')

    # Now build a thread worker that contains as many threads, divided by 2 that have been requested since each bcftools
    # instance takes 2 threads and 1 thread for monitoring
    available_workers = threads - 1
    executor = ThreadPoolExecutor(max_workers=available_workers)

    future_pool = []
    for cram_file in input_cram_reader:
        future_pool.append(executor.submit(process_cram, cram = cram_file, interval_files = interval_files))

    input_cram_reader.close()
    print("All threads submitted...")

    ## Write all coverage values to a single final file using a csv.dictwriter
    output_txt = 'coverage.txt'
    output_gzip = output_file

    output_fh = open(output_txt, "w")
    header = ['sample']
    header.extend(interval_files.keys())
    output_writer = csv.DictWriter(output_fh, delimiter="\t", lineterminator="\n", fieldnames=header)
    output_writer.writeheader()
    for future in futures.as_completed(future_pool):
        try:
            output_writer.writerow(future.result())
        except Exception as err:
            print("A thread failed...")
            print(Exception, err)

    output_fh.close()
    print("All threads completed...")

    # Write output as .gz to save space and store in our project with dxpy
    with open(output_txt, 'rb') as f_in:
        with gzip.open(output_gzip, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    ## Have to do 'upload_local_file' to make sure the new file is registered with dna nexus and uploaded to our project
    output = {"output_file": dxpy.dxlink(dxpy.upload_local_file(output_gzip))}

    return output


dxpy.run()
