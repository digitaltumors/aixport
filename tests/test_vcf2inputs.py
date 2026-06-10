#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import shutil
import sys
import tempfile
import types
import unittest

try:
    import cellmaps_utils  # noqa: F401
except ModuleNotFoundError:
    cellmaps_utils = types.ModuleType('cellmaps_utils')
    cellmaps_utils.__version__ = 'test'

    constants = types.ModuleType('cellmaps_utils.constants')
    constants.ArgParseFormatter = argparse.RawDescriptionHelpFormatter

    logutils = types.ModuleType('cellmaps_utils.logutils')

    def _noop(*args, **kwargs):
        return None

    def _write_task_start_json(outdir=None, start_time=None, version=None, data=None):
        path = os.path.join(outdir, 'task_' + str(start_time) + '_start.json')
        with open(path, 'w') as handle:
            handle.write('{}')

    def _write_task_finish_json(outdir=None, start_time=None, end_time=None, status=None):
        path = os.path.join(outdir, 'task_' + str(start_time) + '_finish.json')
        with open(path, 'w') as handle:
            handle.write('{}')

    logutils.setup_cmd_logging = _noop
    logutils.setup_filelogger = _noop
    logutils.write_task_start_json = _write_task_start_json
    logutils.write_task_finish_json = _write_task_finish_json

    provenance = types.ModuleType('cellmaps_utils.provenance')

    class ProvenanceUtil(object):
        def get_login(self):
            return 'test'

        def register_rocrate(self, outdir, **kwargs):
            with open(os.path.join(outdir, 'ro-crate-metadata.json'), 'w') as handle:
                handle.write('{}')

        def register_software(self, outdir, **kwargs):
            return 'software:test'

        def register_computation(self, outdir, **kwargs):
            return 'computation:test'

    provenance.ProvenanceUtil = ProvenanceUtil
    cellmaps_utils.constants = constants
    cellmaps_utils.logutils = logutils
    sys.modules['cellmaps_utils'] = cellmaps_utils
    sys.modules['cellmaps_utils.constants'] = constants
    sys.modules['cellmaps_utils.logutils'] = logutils
    sys.modules['cellmaps_utils.provenance'] = provenance

from aixport.exceptions import AIxPORTError
from aixport.vcf2inputs import GenePanel
from aixport.vcf2inputs import VCFToInputsTool


class TestVCFToInputsTool(unittest.TestCase):

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def _write_file(self, name, content):
        path = os.path.join(self._temp_dir, name)
        with open(path, 'w') as handle:
            handle.write(content)
        return path

    def _write_gene2ind(self):
        return self._write_file('gene2ind.txt',
                                '0\tABL1\n'
                                '1\tTP53\n'
                                '2\tERBB2\n')

    def _write_vcf(self):
        return self._write_file(
            'calls.vcf',
            '##fileformat=VCFv4.2\n'
            '##INFO=<ID=CSQ,Number=.,Type=String,Description="Consequence annotations. Format: Allele|Consequence|IMPACT|SYMBOL">\n'
            '##INFO=<ID=SVTYPE,Number=1,Type=String,Description="SV type">\n'
            '##INFO=<ID=SYMBOL,Number=1,Type=String,Description="Gene symbol">\n'
            '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n'
            '##FORMAT=<ID=CN,Number=1,Type=Float,Description="Copy number">\n'
            '#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A\tSAMPLE_B\n'
            '1\t100\tmut1\tA\tT\t.\tPASS\tCSQ=T|missense_variant|MODERATE|TP53\tGT\t0/1\t0/0\n'
            '1\t101\tsyn1\tG\tC\t.\tPASS\tCSQ=C|synonymous_variant|LOW|ABL1\tGT\t0/1\t0/1\n'
            '1\t200\tdup1\tN\t<DUP>\t.\tPASS\tSVTYPE=DUP;SYMBOL=ERBB2\tGT\t0/1\t0/0\n'
            '1\t201\tdel1\tN\t<DEL>\t.\tPASS\tSVTYPE=DEL;SYMBOL=ABL1\tGT\t0/0\t0/1\n'
            '1\t202\tcnv1\tN\t<CNV>\t.\tPASS\tSVTYPE=CNV;SYMBOL=TP53\tCN\t3\t1\n')

    def _base_args(self, outdir, profile='aixport'):
        return {'outdir': outdir,
                'skip_logging': True,
                'vcf': self._write_vcf(),
                'output_profile': profile,
                'gene_panel': 'nest_vnn_718',
                'gene2ind': self._write_gene2ind(),
                'sample_map': None,
                'sample': None,
                'annotation_field': 'auto',
                'strict_annotations': False,
                'include_filtered': False,
                'min_gq': None,
                'min_dp': None,
                'mutation_effects': None,
                'cn_neutral_low': 1.5,
                'cn_neutral_high': 2.5,
                'covariates': None,
                'outcomes': None,
                'default_covariates': False,
                'default_outcomes': False}

    @staticmethod
    def _read_lines(path):
        with open(path, 'r') as handle:
            return [line.rstrip('\n') for line in handle]

    def test_builtin_panels_load(self):
        nest_panel = GenePanel.load(panel_id='nest_vnn_718')
        self.assertEqual(718, len(nest_panel.genes))
        mutationprojector_panel = GenePanel.load(panel_id='mutationprojector_mskimpact468')
        self.assertEqual(468, len(mutationprojector_panel.genes))
        self.assertEqual(sorted(mutationprojector_panel.genes),
                         mutationprojector_panel.genes)

    def test_run_aixport_profile(self):
        outdir = os.path.join(self._temp_dir, 'aixport_out')
        tool = VCFToInputsTool(self._base_args(outdir))

        self.assertEqual(0, tool.run())

        self.assertEqual(['0\tSAMPLE_A', '1\tSAMPLE_B'],
                         self._read_lines(os.path.join(outdir, 'cell2ind.txt')))
        self.assertEqual(['0,1,0', '0,0,0'],
                         self._read_lines(os.path.join(outdir, 'cell2mutation.txt')))
        self.assertEqual(['0,1,1', '0,0,0'],
                         self._read_lines(os.path.join(outdir,
                                                       'cell2cnamplification.txt')))
        self.assertEqual(['0,0,0', '1,1,0'],
                         self._read_lines(os.path.join(outdir,
                                                       'cell2cndeletion.txt')))
        self.assertTrue(os.path.isfile(os.path.join(outdir,
                                                    'conversion_report.json')))
        self.assertTrue(os.path.isfile(os.path.join(outdir,
                                                    'variants_used.tsv')))

    def test_run_mutationprojector_profile(self):
        outdir = os.path.join(self._temp_dir, 'mutationprojector_out')
        covariates = self._write_file('covariates.txt',
                                      'sample\tcovariate_0\n'
                                      'SAMPLE_B\t0\n'
                                      'SAMPLE_A\t1\n')
        outcomes = self._write_file('outcomes.txt',
                                    'sample\toutcomes\n'
                                    'SAMPLE_B\t0\n'
                                    'SAMPLE_A\t1\n')
        args = self._base_args(outdir, profile='mutationprojector')
        args['covariates'] = covariates
        args['outcomes'] = outcomes
        tool = VCFToInputsTool(args)

        self.assertEqual(0, tool.run())

        self.assertEqual(['sample\tABL1\tTP53\tERBB2',
                          'SAMPLE_A\t0\t1\t0',
                          'SAMPLE_B\t0\t0\t0'],
                         self._read_lines(os.path.join(outdir, 'mut.txt')))
        self.assertEqual(['sample\tABL1\tTP53\tERBB2',
                          'SAMPLE_A\t0\t1\t1',
                          'SAMPLE_B\t0\t0\t0'],
                         self._read_lines(os.path.join(outdir, 'cna.txt')))
        self.assertEqual(['sample\tABL1\tTP53\tERBB2',
                          'SAMPLE_A\t0\t0\t0',
                          'SAMPLE_B\t1\t1\t0'],
                         self._read_lines(os.path.join(outdir, 'cnd.txt')))
        self.assertEqual(['sample\tcovariate_0',
                          'SAMPLE_A\t1',
                          'SAMPLE_B\t0'],
                         self._read_lines(os.path.join(outdir, 'covariates.txt')))
        self.assertEqual(['sample\toutcomes',
                          'SAMPLE_A\t1',
                          'SAMPLE_B\t0'],
                         self._read_lines(os.path.join(outdir, 'outcomes.txt')))

    def test_mutationprojector_requires_auxiliary_files_or_defaults(self):
        outdir = os.path.join(self._temp_dir, 'missing_aux_out')
        tool = VCFToInputsTool(self._base_args(outdir,
                                              profile='mutationprojector'))

        with self.assertRaises(AIxPORTError) as context:
            tool.run()
        self.assertIn('covariates.txt is required', str(context.exception))

    def test_mutationprojector_default_auxiliary_files(self):
        outdir = os.path.join(self._temp_dir, 'default_aux_out')
        args = self._base_args(outdir, profile='mutationprojector')
        args['default_covariates'] = True
        args['default_outcomes'] = True
        tool = VCFToInputsTool(args)

        self.assertEqual(0, tool.run())

        covariates = self._read_lines(os.path.join(outdir, 'covariates.txt'))
        self.assertEqual('sample\tcovariate_0\tcovariate_1\tcovariate_2\t'
                         'covariate_3\tcovariate_4\tcovariate_5\t'
                         'covariate_6\tcovariate_7\tcovariate_8',
                         covariates[0])
        self.assertEqual(['sample\toutcomes', 'SAMPLE_A\t0', 'SAMPLE_B\t0'],
                         self._read_lines(os.path.join(outdir, 'outcomes.txt')))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
