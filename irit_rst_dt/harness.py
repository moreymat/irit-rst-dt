'''
Paths to files used or generated by the test harness
'''
from collections import Counter
from os import path as fp
import sys

from attelo.fold import (make_n_fold)
from attelo.harness import Harness
from attelo.harness.evaluate import (evaluate_corpus,
                                     prepare_dirs)
from attelo.io import (load_fold_dict,
                       save_fold_dict)
from attelo.parser.intra import (IntraInterPair)
from attelo.util import (mk_rng)

from .local import (CONFIG_FILE,
                    DETAILED_EVALUATIONS,
                    EVALUATIONS,
                    FIXED_FOLD_FILE,
                    GRAPH_DOCS,
                    METRICS,
                    TEST_CORPUS,
                    TEST_EVALUATION_KEY,
                    TRAINING_CORPUS)
from .util import (latest_tmp, exit_ungathered)


# pylint: disable=too-many-arguments, too-many-instance-attributes
class IritHarness(Harness):
    """Test harness configuration using global vars defined in
    local.py
    """

    def __init__(self):
        dataset = fp.basename(TRAINING_CORPUS)
        testset = (fp.basename(TEST_CORPUS) if TEST_CORPUS is not None
                   else None)
        super(IritHarness, self).__init__(dataset, testset)
        self.sanity_check_config()

    def run(self, runcfg):
        """Run the evaluation
        """
        data_dir = latest_tmp()
        if not fp.exists(data_dir):
            exit_ungathered()
        eval_dir, scratch_dir = prepare_dirs(runcfg, data_dir)
        self.load(runcfg, eval_dir, scratch_dir)
        evidence_of_gathered = self.mpack_paths(False)[0]
        if not fp.exists(evidence_of_gathered):
            exit_ungathered()
        evaluate_corpus(self)

    # ------------------------------------------------------
    # local settings
    # ------------------------------------------------------

    @property
    def config_files(self):
        return [CONFIG_FILE]

    @property
    def evaluations(self):
        return EVALUATIONS

    @property
    def detailed_evaluations(self):
        return DETAILED_EVALUATIONS

    # WIP
    @property
    def metrics(self):
        return METRICS
    # end WIP

    @property
    def test_evaluation(self):
        if TEST_CORPUS is None:
            return None
        elif TEST_EVALUATION_KEY is None:
            return None
        test_confs = [x for x in self.evaluations
                      if x.key == TEST_EVALUATION_KEY]
        if test_confs:
            return test_confs[0]
        else:
            return None

    @property
    def graph_docs(self):
        return GRAPH_DOCS

    def create_folds(self, mpack):
        """
        Generate the folds file; return the resulting folds
        """
        if FIXED_FOLD_FILE is None:
            rng = mk_rng()
            fold_dict = make_n_fold(mpack, 10, rng)
        else:
            fold_dict = load_fold_dict(FIXED_FOLD_FILE)
        save_fold_dict(fold_dict, self.fold_file)
        return fold_dict

    # ------------------------------------------------------
    # paths
    # ------------------------------------------------------

    def mpack_paths(self, test_data, stripped=False):
        """
        Parameters
        ----------
        test_data: boolean
            If true, the returned paths point to self.testset else to
            self.dataset.

        Returns
        -------
        path_to_edu_input : string

        path_to_pairings : string

        path_to_features : string

        path_to_vocab : string

        corpus_path : string
            Path to corpus in order to access gold structures (WIP).
        """
        ext = 'relations.sparse'
        # path to data file in the evaluation dir
        dset = self.testset if test_data else self.dataset
        core_path = fp.join(self.eval_dir, "%s.%s" % (dset, ext))
        # WIP gold RST trees
        corpus_path = fp.abspath(TEST_CORPUS if test_data
                                 else TRAINING_CORPUS)
        # end WIP
        return (core_path + '.edu_input',
                core_path + '.pairings',
                (core_path + '.stripped') if stripped else core_path,
                core_path + '.vocab',
                corpus_path)

    def model_paths(self, rconf, fold, parser):
        """Paths to the learner(s) model(s).

        Parameters
        ----------
        rconf : (IntraInterPair of) LearnerConfig
            (Pair) of learner configurations.

            See `attelo.parser.intra.IntraInterPair`,
            `attelo.harness.config.LearnerConfig`

        fold : TODO
            TODO

        parser : parser (WIP)
            For IntraInterParser, enables to know which edges the inter
            model has been fit on.

        Returns
        -------
        paths : dict from string to pathname
            Mapping from learner description to model paths.
        """
        parent_dir = (self.fold_dir_path(fold) if fold is not None
                      else self.combined_dir_path())

        def _eval_model_path(subconf, mtype):
            "Model for a given loop/eval config and fold"
            # basic filename for a model: bname
            rsubconf = (subconf.attach if 'attach' in mtype
                        else subconf.label)
            fn_tmpl = '{dataset}.{learner}.{task}.{ext}'
            bname = fn_tmpl.format(dataset=self.dataset,
                                   learner=rsubconf.key,
                                   task=mtype,
                                   ext='model')
            return fp.join(parent_dir, bname)

        if isinstance(rconf, IntraInterPair):
            # WIP
            sel_inter = parser.payload._sel_inter
            inter_prefixes = {
                'global': '',
                'inter': 'doc-',
                'head_to_head': 'doc_head-',
                'frontier_to_head': 'doc_frontier-',
            }
            # end WIP
            return {
                'inter:attach': _eval_model_path(
                    rconf.inter, inter_prefixes[sel_inter] + "attach"),
                'inter:label': _eval_model_path(
                    rconf.inter, inter_prefixes[sel_inter] + "relate"),
                'intra:attach': _eval_model_path(
                    rconf.intra, "sent-attach"),
                'intra:label': _eval_model_path(
                    rconf.intra, "sent-relate")
            }
        else:
            return {
                'attach': _eval_model_path(rconf, "attach"),
                'label': _eval_model_path(rconf, "relate"),
                'su': _eval_model_path(rconf, "su"),
            }

    # ------------------------------------------------------
    # utility
    # ------------------------------------------------------

    def sanity_check_config(self):
        """
        Die if there's anything odd about the config
        """
        conf_counts = Counter(econf.key for econf in self.evaluations)
        bad_confs = [k for k, v in conf_counts.items() if v > 1]
        if bad_confs:
            oops = ("Sorry, there's an error in your configuration.\n"
                    "I don't dare to start evaluation until you fix it.\n"
                    "ERROR! -----------------vvvv---------------------\n"
                    "The following configurations more than once:\n{}\n"
                    "ERROR! -----------------^^^^^--------------------"
                    "").format("\n".join(bad_confs))
            sys.exit(oops)
        if TEST_EVALUATION_KEY is not None and TEST_CORPUS is None:
            oops = ("Sorry, there's an error in your configuration:\n"
                    "You have requested a test evaluation, but have not "
                    "specified a test corpus to run.\n"
                    "Hint: it's ok to specify a test corpus without "
                    "specifiying a test eval")
            sys.exit(oops)
        if TEST_EVALUATION_KEY is not None and self.test_evaluation is None:
            oops = ("Sorry, there's an error in your configuration.\n"
                    "I don't dare to start evaluation until you fix it.\n"
                    "ERROR! -----------------vvvv---------------------\n"
                    "The test configuration '{}' does not appear in your "
                    "configurations\n"
                    "ERROR! -----------------^^^^^--------------------"
                    "").format(TEST_EVALUATION_KEY)
            sys.exit(oops)
