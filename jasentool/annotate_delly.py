import logging
import pysam
from cyvcf2 import VCF, Writer
from pathlib import Path

LOG = logging.getLogger(__name__)


def annotate_delly_variants(writer, vcf, annotation, annot_chrom=False):
    """Annotate Delly VCF variants with gene/locus_tag from tabix BED."""
    n_annotated = 0
    for variant in vcf:
        chrom = variant.CHROM
        if annot_chrom:
            chrom = list(annotation.contigs)[0]
        genes, locus_tags = [], []
        for rec in annotation.fetch(chrom, variant.start, variant.end, parser=pysam.asTuple()):
            locus_tags.append(rec[3])
            genes.append(rec[4])
        if genes:
            variant.INFO["gene"] = ",".join(genes)
            variant.INFO["locus_tag"] = ",".join(locus_tags)
            n_annotated += 1
        writer.write_record(variant)
    LOG.info("Annotated %d variants", n_annotated)


class AnnotateDelly:
    def run(self, vcf_path: Path, bed_path: Path, output_path: Path):
        if bed_path is None:
            raise ValueError("A BED file is required for annotation")
        annotation = pysam.TabixFile(str(bed_path), parser=pysam.asTuple())
        vcf = VCF(str(vcf_path))

        # Chromosome compatibility check
        first_variant = next(iter(vcf), None)
        annot_chrom = False
        if first_variant is not None:
            contigs = list(annotation.contigs)
            if first_variant.CHROM not in contigs:
                if len(contigs) == 1:
                    annot_chrom = True
                else:
                    raise ValueError(
                        f"Chromosome {first_variant.CHROM!r} not in BED contigs {contigs}"
                    )
        vcf = VCF(str(vcf_path))  # reset
        vcf.add_info_to_header({"ID": "gene", "Number": 1, "Type": "Character",
                                 "Description": "overlapping gene"})
        vcf.add_info_to_header({"ID": "locus_tag", "Number": 1, "Type": "Character",
                                 "Description": "overlapping tbdb locus tag"})
        writer = Writer(str(output_path), vcf)
        annotate_delly_variants(writer, vcf, annotation, annot_chrom=annot_chrom)
        writer.close()
