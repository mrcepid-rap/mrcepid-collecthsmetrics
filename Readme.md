# CollectHsMetrics (DNAnexus Platform App)

This is the source code for an app that runs on the DNAnexus Platform.
For more information about how to run or modify it, see
https://documentation.dnanexus.com/.

### Table of Contents

## Introduction

This applet calculates coverage stats for a single CRAM file based on a set of input intervals using [picard tools](https://broadinstitute.github.io/picard/).

This README makes use of DNANexus file and project naming conventions. Where applicable, an object available on the DNANexus
platform has a hash ID like:

* file – `file-1234567890ABCDEFGHIJKLMN`
* project – `project-1234567890ABCDEFGHIJKLMN`

Information about files and projects can be queried using the `dx describe` tool native to the DNANexus SDK:

```commandline
dx describe file-1234567890ABCDEFGHIJKLMN
```

**Note:** This README pertains to data included as part of the DNANexus project "MRC - Y Chromosome Loss" (project-G50vFK0JJjbf1VJb4gk2vVXX)

### Dependencies

#### Software

The only dependency of this applet is [picard tools](https://broadinstitute.github.io/picard/). Version `2.25.5` of
the source code was downloaded from the picard tools website and compiled as per the picard README. This jar was then
placed into the directory:

`resources/usr/bin`

in accordance with the dependency [instructions](https://documentation.dnanexus.com/developer/apps/dependency-management/asset-build-process)
from DNANexus. All resources stored in this folder are then included with the built app at `/usr/bin/picard.jar`
on the launched AWS instance.

#### Resource Files

This applet uses a set of interval files in the picard [interval list format](https://gatk.broadinstitute.org/hc/en-us/articles/360035531852-Intervals-and-interval-lists)
provided to Eugene Gardner by Yajie Zhao. These files are uploaded with a ["property"](https://documentation.dnanexus.com/developer/api/introduction-to-data-object-metadata/properties)
named "interval_type" that describes the type of interval list and is used to name the header in the primary 
[output](#output) file generated by this applet:

| List type | File | interval_type property | DNANexus file hash |
|-----------------------------------------------------| --------- | -------- | -------- |
| Autosomes | `UKBB_200K_WES_Autosomes.interval_list` | autosome |  file-G33gzBjJXk859gB3FFxFXv6k |
| chrX without PAR regions | `UKBB_200K_WES_chrX_without_PAR.interval_list` | XnoPAR | file-G365Z30JXk8305fy2fPBKgvx |
| chrY | `UKBB_200K_WES_XDR.interval_list` | xdr | file-G365Yv8JXk82523zFY17gJpv

These files were uploaded to the DNANexus platform using a command like (example is for the autosome list):

```commandline
dx upload --path /project_resources/interval_files/ --property interval_type="autosome" UKBB_200K_WES_Autosomes.interval_list
```

All interval files are stored in project-specific folder `/project_resources/interval_files`. 

## Methodology

This applet is mostly a wrapper around the picardtools CollectHsMetrics command. Please see the [documentation](https://gatk.broadinstitute.org/hc/en-us/articles/360036856051-CollectHsMetrics-Picard-)
for CollectHsMetrics for more information on how it works.

This tool injests multiple cram files, finds the associated index for those crams and then runs a picardtools command like:

```commandline
java -Xmx4000M -Xms4000M -jar /usr/bin/picard.jar CollectHsMetrics \
              -VALIDATION_STRINGENCY LENIENT \
              -I sample.cram \
              -BAIT_INTERVALS intervals.interval_list \
              -TARGET_INTERVALS intervals.interval_list \
              -O output_file \
              -R reference.fasta \
              -VERBOSITY ERROR
```

`output_file` is the default picard CollectHsMetrics output. This file is then read into Python and the column 
"MEAN_TARGET_COVERAGE" is extracted and stored.

## Running on DNANexus

### Inputs

This applet requires 2 primary inputs (`cram` and `intervals`). `output_file` is optional. Files can 
be provided as either a path **OR** dx file descriptor (e.g. `file-123456abcde`):

|  Input Option   |  dx type  |  description |
|-----------------|-----------|--------------|
| cram_list       | file       | list of .cram files to process, one .cram per-line                                                     |
| intervals       | array:file | .json array of user-provided `.interval_list` files. See how this looks [below](#command-line-example) |
| output_file     | string     | name of the txt.gz output file **[coverage.txt.gz]**                                                   |

`cram_list` is a file list that **MUST** contain DNANexus file hash keys (e.g. like file-1234567890ABCDEFGHIJ). A simple
way to generate such a list is with the following bash/perl one-liner:

```commandline
dx ls -l "Bulk/Exome sequences/Exome OQFE CRAM files/10/*.cram" | perl -ane 'chomp $_; if ($F[6] =~ /^\((\S+)\)$/) {print "$1\n";}' > cram_list.txt
```

This command will:

1. Find all cram files in the directory `10/` and print in dna nexus "long" format which includes a column for file hash (column 7)
2. Extract the file hash using a perl one-liner and print one file hash per line

The final input file will look something like:

```text
file-1234567890ABCDEFGHIJ
file-2345678901ABCDEFGHIJ
file-3456789012ABCDEFGHIJ
file-4567890123ABCDEFGHIJ
```

This file then needs to be uploaded to the DNANexus platform, so it can be provided as input:

```commandline
dx upload cram_list.txt
```

### Output

The applet provides as output a single .gz file named using the `output_file` input parameter (by default `coverage.txt.gz`).
The first column of the output file is the sample EID, followed by a column for each of the masks provided to `intervals`
named according to the interval_type property as [described above](#resource-files). One row is returned for each
cram file run through this tool:

```text
sample  autosome    XnoPAR  xdr
1234567 57.23124    54.19918    0
8901234 45.91785    27.02918    29.91712
```

### Command line example

If this is your first time running this applet within a project other than "MRC_EPID_450K_read_depth" (project-G6F3238JvzZpKfB7FbbYpX92),
please see our organisational documentation on how to download and build this app on the DNANexus Research Access Platform:

https://github.com/mrcepid-rap

You can run the following to run this applet:

```commandline
dx run mrcepid-collecthsmetrics /
        --priority low
        -icram_list=file-FybvvKjJ8yf65Yx53k17BzJB /
        -iintervals={"file-G33gzBjJXk859gB3FFxFXv6k","file-G365Z30JXk8305fy2fPBKgvx","file-G365Yv8JXk82523zFY17gJpv"}
        -ioutput_file="myrun.txt.gz"
        --destination project_output/
```

Some notes here regarding execution:
1. You will likely want to include the `--priority low` to make sure you don't request a ton of on-demand instances, which 
   are more expensive.

2. The list provided to `-iintervals` is a json-like string that provides the file hashes for the individual interval_files.

3. I have set a sensible (and tested) default for compute resources on DNANexus that is baked into the json used for building the app (at `dxapp.json`)
so setting an instance type is unnecessary. This current default is for a mem2_ssd1_v2_x32 instance (32 CPUs, 128 Gb RAM, 1.2Tb storage).
If necessary to adjust compute resources, one can provide a flag like `--instance-type mem2_ssd1_v2_x8`.
   
4. output-file is not required by default, but is recommended.

### Batch running

This applet supports running multiple cram files at once via multithreading by default. However, there are some considerations:

1. Using the default instance, 31 cram files can be run at once. Thus, if trying to run thousands of cram files, you will 
   want to spread the workload over multiple instances.

2. If changing the default instance **YOU MUST** use at least mem2 instances as picard needs more memory per file (~4Gb) 
   then a mem1 instance can provide.