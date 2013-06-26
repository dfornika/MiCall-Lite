"""
extractV3_with_G2P.py

Generate V3-specific nucleotide sequence from remapped env .seq file
Along with G2PFPR score in the header

Previous step: compress_fasta.py
Following step: determine_proportion_X4.py (Determine %X4 / file with G2P cutoffs)

Input: HIV1B-env.remap.sam.<qCutoff>.fasta.<minCount>.seq
Output: HIV1B-env.remap.sam.<qCutoff>.fasta.<minCount>.seq.V3
"""

# After remapping, dashes introduced into env sequence due to alignment
# Strip out dashes at this step

# Protein translation needed to generate G2P scores
# Correct ORF determined by aligning 3 ORFs against reference V3-prot and keeping highest score
# Calculate G2P score off correct protein translation

import os
import sys
from glob import glob
from Bio import SeqIO
from seqUtils import convert_fasta, translate_nuc
from hyphyAlign import HyPhy, change_settings, refSeqs, pair_align, get_boundaries, apply2nuc
from minG2P import conan_g2p			# conan_g2p(aaseq) returns (g2p, fpr, aligned)

hyphy = HyPhy._THyPhy (os.getcwd(), 1)
change_settings(hyphy) 					# Default settings are for protein alignment

# Reference sequence is V3 in nucleotide space
refseq = translate_nuc(refSeqs['V3, clinical'], 0)
proteinV3RefSeq = "CTRPNNNTRKSIHIGPGRAFYATGEIIGDIRQAHC"

helpOutput = """
Usage: python extractV3_with_G2P.py <qCutoff to process> <folderContainingSeqFiles>

qCutoff 10: python extractV3_with_G2P.py 0 ../../130524_M01841_0004_000000000-A43J1/Data/Intensities/BaseCalls/remap_sams/
"""

if len(sys.argv) != 3:
	print helpOutput
	sys.exit()

# Look at all HIV1B-env seq files
#globPath = sys.argv[1] + '*.HIV1B-env.remap.sam.*.fasta.*.seq'

qCutoff = sys.argv[1]
globPath = sys.argv[2] + '*.HIV1B-env.remap.sam.' + qCutoff + '.fasta.*.seq'
files = glob(globPath)

# For each env-nucleotide unique fasta.seq fasta file
for f in files:
	#if f != '../../130524_M01841_0004_000000000-A43J1/Data/Intensities/BaseCalls/remap_sams/F00131.HIV1B-env.remap.sam.10.fasta.3.seq':
	#	continue

	infile = open(f, 'rU')
	try:
		fasta = convert_fasta(infile.readlines())
	except:
		print 'failed to convert', f
		continue
	infile.close()

	# Output file will contain V3 sequence and g2p data
	outfilename = f + ".v3"

	try:
		# Open file for writing, but fail if file already exists
		fd = os.open(outfilename, os.O_WRONLY | os.O_CREAT | os.O_EXCL)

		# Convert to standard (writable) Python file object
		outfile = os.fdopen(fd, "w")

		# Change permissions to 644 (Leading 0 treats as octal)
		os.chmod(outfilename, 0644)
	except:
		print "Already exists (SKIPPING): " + outfilename
		continue

	print "Writing to file: " + outfilename

	# For each (header, sequence), extract V3
	for header, envSeq in fasta:

		#if header != "F00131_variant_100_count_31":
		#	continue

		envSeq = envSeq.strip("-")				# Strip out dashes generated by alignment
		aaEnvSeq1 = translate_nuc(envSeq, 0)	# Translate env on 3 different ORFs
		aaEnvSeq2 = translate_nuc(envSeq, 1)
		aaEnvSeq3 = translate_nuc(envSeq, 2)
		aquery1, aref1, ascore1 = pair_align(hyphy, proteinV3RefSeq, aaEnvSeq1)
		aquery2, aref2, ascore2 = pair_align(hyphy, proteinV3RefSeq, aaEnvSeq2)
		aquery3, aref3, ascore3 = pair_align(hyphy, proteinV3RefSeq, aaEnvSeq3)
		aaEnvSeq = "";	aquery = "";	aref = "";	ascore = "";

		# Align 3 different ORFs against protein V3 sequence - take best alignment as correct ORF
		if ascore1 >= ascore2 and ascore1 >= ascore3:
			aaEnvSeq = aaEnvSeq1;	aquery = aquery1;	aref = aref1;	ascore = ascore1;
		elif ascore2 >= ascore1 and ascore2 >= ascore3:
			aaEnvSeq = aaEnvSeq2;	aquery = aquery2;	aref = aref2;	ascore = ascore2;
		elif ascore3 >= ascore1 and ascore3 >= ascore2:
			aaEnvSeq = aaEnvSeq3;	aquery = aquery3;	aref = aref3;	ascore = ascore3;

		left, right = get_boundaries(aref)      # Get left/right boundaries of V3 protein
		v3prot = aquery[left:right]             # Extract correct ORF V3 protein - needed for G2P

		# Generate G2P score
		g2p, fpr, aligned = conan_g2p(v3prot)

		# V3nuc may contain gaps as it comes from the alignment of protein(envSeq) to v3prot - ????
		v3nuc = apply2nuc(envSeq[(3*left):], v3prot, aref[left:right], keepIns=True, keepDel=False)
		v3nuc = v3nuc.strip("-")

		# Conditions for dropping data
		# 1) Censored bases were detected ('N')
		# 2) V3 didn't start with C, end with C
		# 3) V3 didn't contain an internal stop codon ('*')
		# 4) Alignment score less than 50

		if 'N' in v3nuc or not v3prot.startswith('C') or not v3prot.endswith('C') or '*' in v3prot or ascore < 50:
			pass
		else:
			header = header + '_G2PFPR_' + str(fpr)
			outfile.write(">" + header)
			outfile.write('\n')
			outfile.write(v3nuc)
			outfile.write('\n')

	outfile.close()
