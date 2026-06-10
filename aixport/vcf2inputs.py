import csv
import gzip
import json
import os
import re
from collections import defaultdict

import aixport
from aixport.basecmdtool import BaseCommandLineTool
from aixport.exceptions import AIxPORTError
import aixport.constants
import cellmaps_utils.constants


DEFAULT_MUTATION_EFFECTS = [
    'missense_variant',
    'stop_gained',
    'stop_lost',
    'start_lost',
    'frameshift_variant',
    'splice_acceptor_variant',
    'splice_donor_variant',
    'protein_altering_variant',
    'inframe_insertion',
    'inframe_deletion'
]

SIMPLE_GENE_FIELDS = ['SYMBOL', 'GENE', 'Gene', 'HUGO']

MUTATION = 'mutation'
CN_AMPLIFICATION = 'copy_number_amplification'
CN_DELETION = 'copy_number_deletion'


class GenePanel(object):
    """
    Loads and validates a gene panel.
    """

    def __init__(self, panel_id=None, genes=None, aliases=None, metadata=None):
        self.panel_id = panel_id
        self.genes = genes or []
        self.aliases = aliases or {}
        self.metadata = metadata or {}
        self.gene_to_index = {gene: idx for idx, gene in enumerate(self.genes)}

    @staticmethod
    def _builtin_panel_dir(panel_id):
        return os.path.join(os.path.dirname(__file__),
                            'data',
                            'gene_panels',
                            panel_id)

    @staticmethod
    def _read_json(path):
        with open(path, 'r') as handle:
            return json.load(handle)

    @staticmethod
    def _load_aliases(path):
        aliases = {}
        if path is None or not os.path.isfile(path):
            return aliases
        with open(path, 'r') as handle:
            reader = csv.DictReader(handle, delimiter='\t')
            if reader.fieldnames is None:
                return aliases
            if 'synonym' not in reader.fieldnames or 'primary' not in reader.fieldnames:
                raise AIxPORTError('Alias file must contain synonym and primary columns')
            for row in reader:
                synonym = row.get('synonym', '').strip()
                primary = row.get('primary', '').strip()
                if synonym and primary:
                    aliases[synonym] = primary
        return aliases

    @staticmethod
    def _load_gene2ind(path):
        entries = []
        with open(path, 'r') as handle:
            for line_number, line in enumerate(handle, 1):
                line = line.strip()
                if line == '':
                    continue
                parts = line.split('\t')
                if len(parts) != 2:
                    raise AIxPORTError('Invalid gene2ind line ' + str(line_number) +
                                        ' in ' + path)
                try:
                    index = int(parts[0])
                except ValueError:
                    raise AIxPORTError('Invalid gene index on line ' + str(line_number) +
                                        ' in ' + path)
                gene = parts[1].strip()
                if gene == '':
                    raise AIxPORTError('Empty gene on line ' + str(line_number) +
                                        ' in ' + path)
                entries.append((index, gene))
        if not entries:
            raise AIxPORTError('Gene panel is empty: ' + path)

        indices = [entry[0] for entry in entries]
        genes = [entry[1] for entry in entries]
        if len(set(indices)) != len(indices):
            raise AIxPORTError('Gene panel has duplicate indices: ' + path)
        if len(set(genes)) != len(genes):
            raise AIxPORTError('Gene panel has duplicate genes: ' + path)
        expected = list(range(len(entries)))
        if sorted(indices) != expected:
            raise AIxPORTError('Gene panel indices must be zero-based and contiguous: ' +
                                path)
        entries = sorted(entries, key=lambda entry: entry[0])
        return [entry[1] for entry in entries]

    @classmethod
    def load(cls, panel_id=None, gene2ind_path=None):
        metadata = {}
        aliases = {}
        if gene2ind_path is not None:
            panel_id = 'custom'
            gene2ind = os.path.abspath(gene2ind_path)
            if not os.path.isfile(gene2ind):
                raise AIxPORTError('gene2ind file does not exist: ' + gene2ind)
        else:
            panel_id = panel_id or 'nest_vnn_718'
            panel_dir = cls._builtin_panel_dir(panel_id)
            if not os.path.isdir(panel_dir):
                raise AIxPORTError('Unknown gene panel: ' + str(panel_id))
            metadata = cls._read_json(os.path.join(panel_dir, 'panel.json'))
            gene2ind = os.path.join(panel_dir, metadata.get('gene2ind', 'gene2ind.txt'))
            aliases = cls._load_aliases(os.path.join(panel_dir,
                                                     metadata.get('aliases',
                                                                  'aliases.tsv')))
        genes = cls._load_gene2ind(gene2ind)
        return cls(panel_id=panel_id,
                   genes=genes,
                   aliases=aliases,
                   metadata=metadata)

    def resolve(self, gene):
        """
        Resolves a gene symbol to a panel gene and index.
        """
        if gene in self.gene_to_index:
            return gene, self.gene_to_index[gene], False
        primary = self.aliases.get(gene)
        if primary is not None and primary in self.gene_to_index:
            return primary, self.gene_to_index[primary], True
        return None, None, False

    def write_gene2ind(self, path):
        with open(path, 'w') as handle:
            for index, gene in enumerate(self.genes):
                handle.write(str(index) + '\t' + gene + '\n')


class SampleMap(object):
    """
    Maps VCF sample names to output sample names.
    """

    def __init__(self, mapping=None):
        self.mapping = mapping or {}

    @classmethod
    def load(cls, path):
        mapping = {}
        if path is None:
            return cls(mapping)
        with open(path, 'r') as handle:
            for line_number, line in enumerate(handle, 1):
                line = line.strip()
                if line == '' or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if line_number == 1 and parts[0] in ('vcf_sample', 'sample'):
                    continue
                if len(parts) != 2:
                    raise AIxPORTError('Sample map must have two tab-delimited columns')
                source = parts[0].strip()
                target = parts[1].strip()
                if source == '' or target == '':
                    raise AIxPORTError('Sample map contains empty sample IDs')
                if source in mapping:
                    raise AIxPORTError('Duplicate VCF sample in sample map: ' + source)
                mapping[source] = target
        if len(set(mapping.values())) != len(mapping.values()):
            raise AIxPORTError('Sample map contains duplicate output sample IDs')
        return cls(mapping)

    def apply(self, vcf_samples, selected_samples=None):
        selected = selected_samples or vcf_samples
        selected_set = set(selected)
        missing = [sample for sample in selected if sample not in vcf_samples]
        if missing:
            raise AIxPORTError('Selected VCF sample is missing: ' + ','.join(missing))
        result = []
        for sample in vcf_samples:
            if sample not in selected_set:
                continue
            result.append((sample, self.mapping.get(sample, sample)))
        output_samples = [entry[1] for entry in result]
        if len(set(output_samples)) != len(output_samples):
            raise AIxPORTError('Duplicate output sample IDs after sample mapping')
        if not result:
            raise AIxPORTError('No VCF samples selected for output')
        return result


class VCFRecord(object):
    """
    Minimal parsed VCF record.
    """

    def __init__(self, line_number=None, chrom=None, pos=None, record_id=None,
                 ref=None, alts=None, qual=None, filter_value=None, info=None,
                 format_keys=None, samples=None):
        self.line_number = line_number
        self.chrom = chrom
        self.pos = pos
        self.record_id = record_id
        self.ref = ref
        self.alts = alts or []
        self.qual = qual
        self.filter_value = filter_value
        self.info = info or {}
        self.format_keys = format_keys or []
        self.samples = samples or {}

    def info_values(self, key):
        value = self.info.get(key)
        if value is None:
            return []
        if value is True:
            return [True]
        if isinstance(value, list):
            return value
        return [value]

    def info_first(self, key):
        values = self.info_values(key)
        if not values:
            return None
        return values[0]


class VCFParser(object):
    """
    Small VCF v4.2 parser for annotated, genotype-bearing VCF files.
    """

    INFO_RE = re.compile(r'##INFO=<(.+)>')

    def __init__(self, path):
        self.path = os.path.abspath(path)
        if not os.path.isfile(self.path):
            raise AIxPORTError('VCF file does not exist: ' + self.path)
        self.samples = []
        self.info_descriptions = {}
        self._read_header()

    def _open(self):
        if self.path.endswith('.gz'):
            return gzip.open(self.path, 'rt')
        return open(self.path, 'r')

    @staticmethod
    def _split_meta_parts(text):
        parts = []
        current = []
        in_quote = False
        for char in text:
            if char == '"':
                in_quote = not in_quote
            if char == ',' and not in_quote:
                parts.append(''.join(current))
                current = []
                continue
            current.append(char)
        parts.append(''.join(current))
        return parts

    def _parse_info_meta(self, line):
        match = self.INFO_RE.match(line)
        if match is None:
            return
        fields = {}
        for part in self._split_meta_parts(match.group(1)):
            if '=' not in part:
                continue
            key, value = part.split('=', 1)
            fields[key] = value.strip('"')
        info_id = fields.get('ID')
        if info_id:
            self.info_descriptions[info_id] = fields.get('Description', '')

    def _read_header(self):
        with self._open() as handle:
            for line in handle:
                line = line.rstrip('\n')
                if line.startswith('##INFO='):
                    self._parse_info_meta(line)
                    continue
                if line.startswith('#CHROM'):
                    fields = line.split('\t')
                    if len(fields) > 9:
                        self.samples = fields[9:]
                    return
        raise AIxPORTError('VCF is missing #CHROM header: ' + self.path)

    @staticmethod
    def _parse_info(info_text):
        info = {}
        if info_text in ('', '.'):
            return info
        for item in info_text.split(';'):
            if item == '':
                continue
            if '=' not in item:
                info[item] = True
                continue
            key, value = item.split('=', 1)
            if ',' in value:
                info[key] = value.split(',')
            else:
                info[key] = value
        return info

    def records(self):
        with self._open() as handle:
            for line_number, line in enumerate(handle, 1):
                if line.startswith('#'):
                    continue
                line = line.rstrip('\n')
                if line == '':
                    continue
                fields = line.split('\t')
                if len(fields) < 8:
                    raise AIxPORTError('Invalid VCF record at line ' + str(line_number))
                alts = [] if fields[4] in ('', '.') else fields[4].split(',')
                format_keys = fields[8].split(':') if len(fields) > 8 else []
                samples = {}
                for sample_name, sample_text in zip(self.samples, fields[9:]):
                    sample_values = sample_text.split(':') if sample_text else []
                    sample_data = {}
                    for index, key in enumerate(format_keys):
                        if index < len(sample_values):
                            sample_data[key] = sample_values[index]
                    samples[sample_name] = sample_data
                yield VCFRecord(line_number=line_number,
                                chrom=fields[0],
                                pos=fields[1],
                                record_id=fields[2],
                                ref=fields[3],
                                alts=alts,
                                qual=fields[5],
                                filter_value=fields[6],
                                info=self._parse_info(fields[7]),
                                format_keys=format_keys,
                                samples=samples)


class Annotation(object):
    """
    Gene annotation from a VCF INFO field.
    """

    def __init__(self, gene=None, effects=None, allele=None, source=None, raw=None):
        self.gene = gene
        self.effects = effects or []
        self.allele = allele
        self.source = source
        self.raw = raw


class VCFAnnotationExtractor(object):
    """
    Extracts gene and consequence annotations from VCF INFO fields.
    """

    def __init__(self, info_descriptions=None, field='auto',
                 strict_annotations=False):
        self.info_descriptions = info_descriptions or {}
        self.field = field or 'auto'
        self.strict_annotations = strict_annotations

    @staticmethod
    def _format_fields_from_description(description):
        if description is None or 'Format:' not in description:
            return []
        fmt = description.split('Format:', 1)[1].strip()
        fmt = fmt.strip(' "\'')
        if fmt.endswith('.'):
            fmt = fmt[:-1]
        return [part.strip(" '\"") for part in fmt.split('|')]

    @staticmethod
    def _index_of(fields, names):
        for name in names:
            if name in fields:
                return fields.index(name)
        return None

    def _get_format_indices(self, field):
        description = self.info_descriptions.get(field)
        fields = self._format_fields_from_description(description)
        if not fields:
            if self.strict_annotations:
                raise AIxPORTError('Unable to parse annotation metadata for INFO/' +
                                    field)
            if field == 'CSQ':
                fields = ['Allele', 'Consequence', 'IMPACT', 'SYMBOL']
            elif field == 'ANN':
                fields = ['Allele', 'Annotation', 'Annotation_Impact',
                          'Gene_Name']
            else:
                return None
        return {'allele': self._index_of(fields, ['Allele']),
                'effect': self._index_of(fields, ['Consequence',
                                                  'Annotation']),
                'gene': self._index_of(fields, ['SYMBOL',
                                                'Gene_Name',
                                                'Gene',
                                                'HUGO'])}

    @staticmethod
    def _split_effects(value):
        if value is None or value == '':
            return []
        effects = []
        for part in re.split(r'[&,]', value):
            part = part.strip()
            if part:
                effects.append(part)
        return effects

    def _extract_structured(self, record, field):
        indices = self._get_format_indices(field)
        if indices is None or indices.get('gene') is None:
            if self.strict_annotations:
                raise AIxPORTError('Unable to locate gene field for INFO/' + field)
            return []
        annotations = []
        for value in record.info_values(field):
            if value is True:
                continue
            parts = str(value).split('|')
            gene_idx = indices.get('gene')
            effect_idx = indices.get('effect')
            allele_idx = indices.get('allele')
            gene = parts[gene_idx].strip() if gene_idx < len(parts) else ''
            if gene == '':
                continue
            effect_value = parts[effect_idx] if effect_idx is not None and effect_idx < len(parts) else ''
            allele = parts[allele_idx] if allele_idx is not None and allele_idx < len(parts) else None
            annotations.append(Annotation(gene=gene,
                                          effects=self._split_effects(effect_value),
                                          allele=allele,
                                          source=field,
                                          raw=str(value)))
        return annotations

    @staticmethod
    def _extract_simple(record, field):
        annotations = []
        for value in record.info_values(field):
            if value is True:
                continue
            gene = str(value).strip()
            if gene == '':
                continue
            annotations.append(Annotation(gene=gene,
                                          effects=['protein_altering_variant'],
                                          source=field,
                                          raw=gene))
        return annotations

    def _choose_auto_field(self, record):
        for field in ['CSQ', 'ANN']:
            if record.info_values(field):
                return field
        for field in SIMPLE_GENE_FIELDS:
            if record.info_values(field):
                return field
        return None

    def extract(self, record):
        field = self.field
        if field == 'auto':
            field = self._choose_auto_field(record)
        if field is None:
            if self.strict_annotations:
                raise AIxPORTError('No supported annotation field found at VCF line ' +
                                    str(record.line_number))
            return []
        if field in ('CSQ', 'ANN'):
            return self._extract_structured(record, field)
        if not record.info_values(field):
            if self.strict_annotations:
                raise AIxPORTError('INFO/' + field + ' missing at VCF line ' +
                                    str(record.line_number))
            return []
        return self._extract_simple(record, field)


class VariantClassifier(object):
    """
    Classifies VCF record/sample/annotation combinations into model events.
    """

    def __init__(self, mutation_effects=None, min_gq=None, min_dp=None,
                 cn_neutral_low=1.5, cn_neutral_high=2.5):
        self.mutation_effects = set(mutation_effects or DEFAULT_MUTATION_EFFECTS)
        self.min_gq = min_gq
        self.min_dp = min_dp
        self.cn_neutral_low = cn_neutral_low
        self.cn_neutral_high = cn_neutral_high

    @staticmethod
    def _float_value(value):
        if value is None or value in ('', '.'):
            return None
        try:
            return float(str(value).split(',')[0])
        except ValueError:
            return None

    @staticmethod
    def _genotype_alleles(gt):
        if gt is None or gt in ('', '.', './.', '.|.'):
            return []
        alleles = []
        for part in re.split(r'[/|]', gt):
            if part in ('', '.'):
                continue
            try:
                alleles.append(int(part))
            except ValueError:
                continue
        return alleles

    def _called_alt_alleles(self, record, sample_data):
        alleles = self._genotype_alleles(sample_data.get('GT'))
        called = set()
        for allele in alleles:
            if allele <= 0:
                continue
            alt_index = allele - 1
            if alt_index < len(record.alts):
                called.add(record.alts[alt_index])
        return called

    def _is_non_reference(self, sample_data):
        return any(allele > 0 for allele in self._genotype_alleles(sample_data.get('GT')))

    def _passes_sample_filters(self, sample_data):
        if self.min_gq is not None:
            gq = self._float_value(sample_data.get('GQ'))
            if gq is not None and gq < self.min_gq:
                return False, 'low_gq'
        if self.min_dp is not None:
            dp = self._float_value(sample_data.get('DP'))
            if dp is not None and dp < self.min_dp:
                return False, 'low_dp'
        return True, None

    @staticmethod
    def _alt_event_types(record):
        types = set()
        svtype = record.info_first('SVTYPE')
        if svtype is not None and svtype is not True:
            types.add(str(svtype).upper())
        for alt in record.alts:
            types.add(alt.strip('<>').upper())
        return types

    def classify(self, record, sample_data, annotation):
        if not sample_data:
            return None, 'missing_genotype', ''
        passed, reason = self._passes_sample_filters(sample_data)
        if not passed:
            return None, reason, ''

        cn = self._float_value(sample_data.get('CN'))
        if cn is not None:
            if cn < self.cn_neutral_low:
                return CN_DELETION, None, 'FORMAT/CN=' + str(cn)
            if cn > self.cn_neutral_high:
                return CN_AMPLIFICATION, None, 'FORMAT/CN=' + str(cn)
            return None, 'neutral_copy_number', 'FORMAT/CN=' + str(cn)

        if sample_data.get('GT') in (None, '', '.', './.', '.|.'):
            return None, 'missing_genotype', ''
        if not self._is_non_reference(sample_data):
            return None, 'reference_genotype', ''

        event_types = self._alt_event_types(record)
        if 'DEL' in event_types:
            return CN_DELETION, None, 'SVTYPE/ALT=DEL'
        if 'DUP' in event_types:
            return CN_AMPLIFICATION, None, 'SVTYPE/ALT=DUP'
        if 'CNV' in event_types:
            return None, 'unsupported_cnv', 'SVTYPE/ALT=CNV'

        if annotation.allele not in (None, ''):
            called = self._called_alt_alleles(record, sample_data)
            if called and annotation.allele not in called:
                return None, 'uncalled_allele_annotation', annotation.allele

        if self.mutation_effects.intersection(set(annotation.effects)):
            return MUTATION, None, ','.join(annotation.effects)
        return None, 'non_protein_altering', ','.join(annotation.effects)


class FeatureMatrixBuilder(object):
    """
    Maintains the three binary feature matrices.
    """

    def __init__(self, panel=None, sample_pairs=None):
        self.panel = panel
        self.sample_pairs = sample_pairs or []
        self.vcf_samples = [entry[0] for entry in self.sample_pairs]
        self.output_samples = [entry[1] for entry in self.sample_pairs]
        self.sample_index = {entry[0]: index for index, entry in enumerate(self.sample_pairs)}
        self.matrices = {
            MUTATION: self._zero_matrix(),
            CN_AMPLIFICATION: self._zero_matrix(),
            CN_DELETION: self._zero_matrix()
        }

    def _zero_matrix(self):
        return [[0 for _ in self.panel.genes] for _ in self.sample_pairs]

    def set_event(self, vcf_sample, gene, event_type):
        row = self.sample_index[vcf_sample]
        _, column, _ = self.panel.resolve(gene)
        if column is None:
            raise AIxPORTError('Cannot set event for non-panel gene: ' + str(gene))
        self.matrices[event_type][row][column] = 1

    def row_for_sample(self, output_sample):
        return self.output_samples.index(output_sample)


class ConversionReport(object):
    """
    Accumulates conversion counters and audit rows.
    """

    def __init__(self, command_options=None, panel=None, samples=None):
        self.command_options = command_options or {}
        self.panel = panel
        self.samples = samples or []
        self.counters = defaultdict(int)
        self.used_events = []
        self.skipped_events = []
        self.extra = {}

    @staticmethod
    def _record_fields(record):
        return {'chrom': record.chrom,
                'pos': record.pos,
                'id': record.record_id,
                'ref': record.ref,
                'alt': ','.join(record.alts)}

    def skip(self, record, reason, sample='', gene='', detail=''):
        self.counters['skipped_' + reason] += 1
        row = self._record_fields(record)
        row.update({'sample': sample,
                    'gene': gene,
                    'reason': reason,
                    'detail': detail})
        self.skipped_events.append(row)

    def used(self, record, sample, source_gene, panel_gene, event_type,
             source='', effects='', detail=''):
        self.counters['used_events'] += 1
        self.counters['used_' + event_type] += 1
        row = self._record_fields(record)
        row.update({'sample': sample,
                    'source_gene': source_gene,
                    'panel_gene': panel_gene,
                    'event_type': event_type,
                    'annotation_source': source,
                    'effects': effects,
                    'detail': detail})
        self.used_events.append(row)

    def write(self, outdir):
        report = {'command_options': self.command_options,
                  'panel_id': self.panel.panel_id if self.panel else None,
                  'panel_gene_count': len(self.panel.genes) if self.panel else 0,
                  'samples': self.samples,
                  'sample_count': len(self.samples),
                  'counters': dict(self.counters),
                  'extra': self.extra}
        with open(os.path.join(outdir, 'conversion_report.json'), 'w') as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write('\n')
        self._write_tsv(os.path.join(outdir, 'variants_used.tsv'),
                        ['chrom', 'pos', 'id', 'ref', 'alt', 'sample',
                         'source_gene', 'panel_gene', 'event_type',
                         'annotation_source', 'effects', 'detail'],
                        self.used_events)
        self._write_tsv(os.path.join(outdir, 'variants_skipped.tsv'),
                        ['chrom', 'pos', 'id', 'ref', 'alt', 'sample',
                         'gene', 'reason', 'detail'],
                        self.skipped_events)

    @staticmethod
    def _write_tsv(path, fieldnames, rows):
        with open(path, 'w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter='\t',
                                    extrasaction='ignore')
            writer.writeheader()
            for row in rows:
                writer.writerow(row)


class OutputWriter(object):
    """
    Base profile-specific writer.
    """

    def write(self, outdir, panel, builder, report):
        raise NotImplementedError('subclasses need to implement')


class AIxPORTOutputWriter(OutputWriter):
    """
    Writes the current AIxPORT genomic feature files.
    """

    def write(self, outdir, panel, builder, report):
        panel.write_gene2ind(os.path.join(outdir, aixport.constants.GENE2IND))
        with open(os.path.join(outdir, aixport.constants.CELL2IND), 'w') as handle:
            for index, sample in enumerate(builder.output_samples):
                handle.write(str(index) + '\t' + sample + '\n')
        self._write_matrix(os.path.join(outdir, aixport.constants.CELL2MUTATION),
                           builder.matrices[MUTATION])
        self._write_matrix(os.path.join(outdir, aixport.constants.CELL2CNAMPLIFICATION),
                           builder.matrices[CN_AMPLIFICATION])
        self._write_matrix(os.path.join(outdir, aixport.constants.CELL2CNDELETION),
                           builder.matrices[CN_DELETION])

    @staticmethod
    def _write_matrix(path, matrix):
        with open(path, 'w') as handle:
            for row in matrix:
                handle.write(','.join([str(value) for value in row]) + '\n')


class MutationProjectorOutputWriter(OutputWriter):
    """
    Writes MutationProjector downstream dataset files.
    """

    def __init__(self, covariates=None, outcomes=None,
                 default_covariates=False, default_outcomes=False):
        self.covariates = covariates
        self.outcomes = outcomes
        self.default_covariates = default_covariates
        self.default_outcomes = default_outcomes

    def write(self, outdir, panel, builder, report):
        sample_order = sorted(builder.output_samples)
        self._write_profile_matrix(os.path.join(outdir, 'mut.txt'), panel, builder,
                                   sample_order, MUTATION)
        self._write_profile_matrix(os.path.join(outdir, 'cna.txt'), panel, builder,
                                   sample_order, CN_AMPLIFICATION)
        self._write_profile_matrix(os.path.join(outdir, 'cnd.txt'), panel, builder,
                                   sample_order, CN_DELETION)
        self._write_auxiliary(outdir, 'covariates.txt', self.covariates,
                              self.default_covariates, sample_order,
                              report, self._default_covariate_row)
        self._write_auxiliary(outdir, 'outcomes.txt', self.outcomes,
                              self.default_outcomes, sample_order,
                              report, self._default_outcome_row)

    @staticmethod
    def _write_profile_matrix(path, panel, builder, sample_order, event_type):
        with open(path, 'w', newline='') as handle:
            writer = csv.writer(handle, delimiter='\t')
            writer.writerow(['sample'] + panel.genes)
            for sample in sample_order:
                row_index = builder.row_for_sample(sample)
                writer.writerow([sample] + builder.matrices[event_type][row_index])

    @staticmethod
    def _read_tsv(path):
        with open(path, 'r', newline='') as handle:
            reader = csv.DictReader(handle, delimiter='\t')
            if reader.fieldnames is None or 'sample' not in reader.fieldnames:
                raise AIxPORTError(path + ' must contain a sample column')
            rows = list(reader)
        return reader.fieldnames, rows

    @staticmethod
    def _default_covariate_row(sample):
        row = {'sample': sample}
        for index in range(9):
            row['covariate_' + str(index)] = '0'
        return row

    @staticmethod
    def _default_outcome_row(sample):
        return {'sample': sample, 'outcomes': '0'}

    def _write_auxiliary(self, outdir, filename, source_path, use_default,
                         sample_order, report, default_row_factory):
        destination = os.path.join(outdir, filename)
        if source_path is None:
            if not use_default:
                raise AIxPORTError(filename + ' is required for MutationProjector '
                                    'output unless the matching default flag is set')
            rows = [default_row_factory(sample) for sample in sample_order]
            fieldnames = list(rows[0].keys()) if rows else ['sample']
            report.extra[filename + '_defaulted'] = True
        else:
            fieldnames, rows = self._read_tsv(source_path)
            row_by_sample = {}
            for row in rows:
                sample = row.get('sample')
                if sample in row_by_sample:
                    raise AIxPORTError(source_path + ' contains duplicate sample ' +
                                        sample)
                row_by_sample[sample] = row
            missing = [sample for sample in sample_order if sample not in row_by_sample]
            extras = [sample for sample in row_by_sample if sample not in sample_order]
            if missing or extras:
                raise AIxPORTError(source_path + ' samples do not match generated '
                                    'genomic samples')
            rows = [row_by_sample[sample] for sample in sample_order]
            report.extra[filename + '_reordered_to_match_genomics'] = True

        with open(destination, 'w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter='\t',
                                    extrasaction='ignore')
            writer.writeheader()
            for row in rows:
                writer.writerow(row)


class VCFToInputsTool(BaseCommandLineTool):
    """
    Converts VCF calls into supported model genomic input matrices.
    """

    COMMAND = 'vcf2inputs'

    def __init__(self, theargs, provenance_utils=None):
        super().__init__(theargs, provenance_utils=provenance_utils)

    @staticmethod
    def _parse_mutation_effects(value):
        if value is None or str(value).strip() == '':
            return DEFAULT_MUTATION_EFFECTS
        return [effect.strip() for effect in str(value).split(',') if effect.strip()]

    @staticmethod
    def _filter_passes(record, include_filtered):
        if include_filtered:
            return True
        return record.filter_value in ('PASS', '.', '')

    def _build_writer(self):
        profile = self._theargs['output_profile']
        if profile in ('aixport', 'nest_vnn'):
            return AIxPORTOutputWriter()
        if profile == 'mutationprojector':
            if self._theargs.get('covariates') and self._theargs.get('default_covariates'):
                raise AIxPORTError('Use either --covariates or --default-covariates')
            if self._theargs.get('outcomes') and self._theargs.get('default_outcomes'):
                raise AIxPORTError('Use either --outcomes or --default-outcomes')
            return MutationProjectorOutputWriter(
                covariates=self._theargs.get('covariates'),
                outcomes=self._theargs.get('outcomes'),
                default_covariates=self._theargs.get('default_covariates', False),
                default_outcomes=self._theargs.get('default_outcomes', False))
        raise AIxPORTError('Unknown output profile: ' + str(profile))

    def run(self):
        exitcode = 99
        try:
            self._initialize_rocrate()
            panel = GenePanel.load(panel_id=self._theargs.get('gene_panel'),
                                   gene2ind_path=self._theargs.get('gene2ind'))
            parser = VCFParser(self._theargs['vcf'])
            if not parser.samples:
                raise AIxPORTError('VCF has no genotype sample columns')
            sample_map = SampleMap.load(self._theargs.get('sample_map'))
            sample_pairs = sample_map.apply(parser.samples,
                                            self._theargs.get('sample'))
            builder = FeatureMatrixBuilder(panel=panel, sample_pairs=sample_pairs)
            report = ConversionReport(command_options=self._report_options(),
                                      panel=panel,
                                      samples=builder.output_samples)
            extractor = VCFAnnotationExtractor(
                info_descriptions=parser.info_descriptions,
                field=self._theargs.get('annotation_field', 'auto'),
                strict_annotations=self._theargs.get('strict_annotations', False))
            classifier = VariantClassifier(
                mutation_effects=self._parse_mutation_effects(
                    self._theargs.get('mutation_effects')),
                min_gq=self._theargs.get('min_gq'),
                min_dp=self._theargs.get('min_dp'),
                cn_neutral_low=self._theargs.get('cn_neutral_low'),
                cn_neutral_high=self._theargs.get('cn_neutral_high'))

            for record in parser.records():
                report.counters['records_read'] += 1
                if not self._filter_passes(record,
                                           self._theargs.get('include_filtered',
                                                             False)):
                    report.skip(record, 'filtered_record',
                                detail=record.filter_value)
                    continue
                annotations = extractor.extract(record)
                if not annotations:
                    report.skip(record, 'no_gene_annotation')
                    continue
                resolved = []
                for annotation in annotations:
                    panel_gene, _, alias_used = panel.resolve(annotation.gene)
                    if panel_gene is None:
                        report.skip(record, 'non_panel_gene', gene=annotation.gene)
                        continue
                    resolved.append((annotation, panel_gene, alias_used))
                if not resolved:
                    continue

                for vcf_sample, output_sample in sample_pairs:
                    sample_data = record.samples.get(vcf_sample, {})
                    for annotation, panel_gene, alias_used in resolved:
                        event, reason, detail = classifier.classify(record,
                                                                    sample_data,
                                                                    annotation)
                        if event is None:
                            report.skip(record, reason,
                                        sample=output_sample,
                                        gene=annotation.gene,
                                        detail=detail)
                            continue
                        builder.set_event(vcf_sample, panel_gene, event)
                        used_detail = detail
                        if alias_used:
                            used_detail = (used_detail + ';' if used_detail else '') + \
                                          'alias_used'
                        report.used(record,
                                    sample=output_sample,
                                    source_gene=annotation.gene,
                                    panel_gene=panel_gene,
                                    event_type=event,
                                    source=annotation.source,
                                    effects=','.join(annotation.effects),
                                    detail=used_detail)

            writer = self._build_writer()
            writer.write(self._theargs['outdir'], panel, builder, report)
            report.write(self._theargs['outdir'])
            self._finalize_rocrate()
            exitcode = 0
            return exitcode
        finally:
            self._write_task_finish_json(exitcode)

    def _report_options(self):
        keys = ['vcf', 'output_profile', 'gene_panel', 'gene2ind',
                'sample_map', 'sample', 'annotation_field',
                'strict_annotations', 'include_filtered', 'min_gq', 'min_dp',
                'mutation_effects', 'cn_neutral_low', 'cn_neutral_high',
                'covariates', 'outcomes', 'default_covariates',
                'default_outcomes']
        return {key: self._theargs.get(key) for key in keys}

    @staticmethod
    def add_subparser(subparsers):
        desc = """

        Version {version}

        {cmd} converts an annotated VCF into genomic model input matrices
        """.format(version=aixport.__version__,
                   cmd=VCFToInputsTool.COMMAND)

        parser = subparsers.add_parser(
            VCFToInputsTool.COMMAND,
            help='Converts VCF calls into model genomic inputs',
            description=desc,
            formatter_class=cellmaps_utils.constants.ArgParseFormatter)

        parser.add_argument('outdir',
                            help='Output directory. This directory should not already exist')
        parser.add_argument('--vcf', required=True,
                            help='Path to annotated VCF or VCF.GZ')
        parser.add_argument('--output-profile',
                            choices=['aixport', 'nest_vnn', 'mutationprojector'],
                            default='aixport',
                            help='Output file layout to write')
        parser.add_argument('--gene-panel', default='nest_vnn_718',
                            help='Bundled gene panel ID')
        parser.add_argument('--gene2ind',
                            help='Custom gene2ind.txt path. Overrides --gene-panel')
        parser.add_argument('--sample-map',
                            help='Two-column TSV mapping VCF sample IDs to output sample IDs')
        parser.add_argument('--sample', action='append',
                            help='VCF sample ID to include. Can be repeated')
        parser.add_argument('--annotation-field', default='auto',
                            help='INFO annotation field to use: auto, CSQ, ANN, SYMBOL, etc.')
        parser.add_argument('--strict-annotations', action='store_true',
                            help='Fail when requested annotation metadata is missing')
        parser.add_argument('--include-filtered', action='store_true',
                            help='Include records whose FILTER is not PASS or .')
        parser.add_argument('--min-gq', type=int,
                            help='Minimum sample GQ when FORMAT/GQ is present')
        parser.add_argument('--min-dp', type=int,
                            help='Minimum sample DP when FORMAT/DP is present')
        parser.add_argument('--mutation-effects',
                            help='Comma-delimited consequence terms counted as mutation')
        parser.add_argument('--cn-neutral-low', type=float, default=1.5,
                            help='Copy number below this threshold is a deletion')
        parser.add_argument('--cn-neutral-high', type=float, default=2.5,
                            help='Copy number above this threshold is an amplification')
        parser.add_argument('--covariates',
                            help='MutationProjector covariates.txt to copy/reorder')
        parser.add_argument('--outcomes',
                            help='MutationProjector outcomes.txt to copy/reorder')
        parser.add_argument('--default-covariates', action='store_true',
                            help='Generate zero-valued MutationProjector covariates')
        parser.add_argument('--default-outcomes', action='store_true',
                            help='Generate zero-valued MutationProjector outcomes')
        return parser
