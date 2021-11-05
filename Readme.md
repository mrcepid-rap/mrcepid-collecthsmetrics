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

This tool injests a single cram file, finds the associated index for that cram and then runs a picardtools command like:

```commandline
java -Xmx4000M -Xms4000M -jar /usr/bin/picard.jar CollectHsMetrics \
              VALIDATION_STRINGENCY=LENIENT \
              I=sample.cram \
              BAIT_INTERVALS=intervals.interval_list \
              TARGET_INTERVALS=intervals.interval_list \
              O=output_file \
              R=reference.fasta
```

`output_file` is the default picard CollectHsMetrics output. This file is then read into Python and the column 
"MEAN_TARGET_COVERAGE" is extracted and stored.

## Running on DNANexus

### Inputs

This applet requires 3 primary inputs. All files can be provided as either a path **OR** dx file descriptor (e.g. `file-123456abcde`):

|  Input Option   |  dx type  |  description |
|-----------------|-----------|--------------|
| -icram         | file       | .cram file                          |
| -iintervals    | array:file | .json array of user-provided `.interval_list` files. See how this looks [below](#command-line-example) |

### Output

The applet provides as output a single .gz file of the form `sample_<EID>.coverage.txt.gz`, where <EID> is the UKBB sample
ID provided by the dx file property 'eid' from the input cram file (i.e. -icram). This same field can be derived on the 
command line by running a command like:

```
dx describe file-123456abcde
```

where `file-123456abcde` is a dx file descriptor of a cram file. The eid can be seen in the 'properties' field.

The first column of the output file is the sample EID, followed by a column for each of the masks provided to `-iintervals`
named according to the interval_type property as [described above](#resource-files). Only one row is returned for each
cram file run through this tool.

### Command line example

If this is your first time running this applet within a project other than "MRC - Y Chromosome Loss" (project-G50vFK0JJjbf1VJb4gk2vVXX),
please see our organisational documentation on how to download and build this app on the DNANexus Research Access Platform:

https://github.com/mrcepid-rap

You can run the following to run this applet:

```commandline
dx run mrcepid-collecthsmetrics /
        -icram=file-FybvvKjJ8yf65Yx53k17BzJB /
        -iintervals={"file-G33gzBjJXk859gB3FFxFXv6k","file-G365Z30JXk8305fy2fPBKgvx","file-G365Yv8JXk82523zFY17gJpv"}
        --destination project_output/
```

Some notes here regarding execution:
1. The list provided to `-iintervals` is a json-like string that provides the file hashes for the individual interval_files. 

2. Outputs are automatically named based on the prefix of the input vcf full path (this is regardless of if you use hash or full path). So
the primary VCF output for the above command-line will be `sample_1000020.coverage.txt`. All outputs will be named using a similar convention.

3. I have set a sensible (and tested) default for compute resources on DNANexus that is baked into the json used for building the app (at `dxapp.json`)
so setting an instance type is unnecessary. This current default is for a mem2_ssd1_v2_x2 instance (2 CPUs, 4 Gb RAM, 75Gb storage).
If necessary to adjust compute resources, one can provide a flag like `--instance-type mem1_ssd1_v2_x8`.

This app uses a mem2_ssd1_v2_x2 instance by default (2 cpus, 8Gb mem, 75Gb SSD). This should be sufficient for any WES sample.

### Batch running

To run multiple files at once (i.e. in batch), the user needs to create a batch file. DNA Nexus have developed a tool 
which does this automatically. An example follows which generates batch files for all cram files in folder `10/`:

```commandline
dx generate_batch_inputs --path "Bulk/Exome sequences/Exome OQFE CRAM files/10/" -icram='(.*)_23153_0_0(\.cram)$''
```

**Note:** The above path to cram files is likely to become outdated as new data is released. I will either update this 
example or you will have to modify accordingly.

**Note:** The goofy thing about the batch input file generated by this is it generates a different batch ID for each run.
I think it might be good to modify to a single batch input like:

```commandline
grep 'batch'  dx_batch.0001.tsv > header.txt
grep -v 'batch' dx_batch.*.tsv | perl -ane 'if ($F[0] =~ /dx_batch.(\d+)\.tsv/) {$F[0] = $1; print join("\t", @F) . "\n";}' > dx_batch.all.tsv
cat header.txt dx_batch.all.tsv > dx_batch.all.header.tsv
```

And then execute the standard command line as above, but modified to use this file:

```commandline
dx run mrcepid-collecthsmetrics /
        --priority low
        --batch-tsv dx_batch.0008.tsv /
        --destination project_output/ /
        --batch-folders /
        -iintervals={"file-G33gzBjJXk859gB3FFxFXv6k","file-G365Z30JXk8305fy2fPBKgvx","file-G365Yv8JXk82523zFY17gJpv"}
```

**Remember:** You will likely want to include the `--priority low` to make sure you don't request a ton of on-demand instances
