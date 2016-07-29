# Author: Eric Kow
# License: CeCILL-B (French BSD3-like)

"""
gather features
"""

from __future__ import print_function
import os

from attelo.harness.util import call, force_symlink

from ..local import (FEATURE_SET, LABEL_SET, TEST_CORPUS, TRAINING_CORPUS,
                     SAME_UNIT, PTB_DIR, CORENLP_OUT_DIR, LECSIE_DATA_DIR)
from ..util import (current_tmp, latest_tmp)

NAME = 'gather'


def config_argparser(psr):
    """Subcommand flags.

    You should create and pass in the subparser to which the flags
    are to be added.

    Notes
    -----
    Could we remove intermediary layers and indirections?
    For example, this script is a wrapper around
    `educe.rst_dt.learning.cmd.extract`.
    This means we need to explicitly expose some (or all?) of the
    arguments of the latter script in the current one.
    This does not look like a good idea.
    """
    psr.add_argument('--skip-training',
                     action='store_true',
                     help='only gather test data')
    psr.add_argument('--fix_pseudo_rels',
                     action='store_true',
                     help='fix pseudo-relation labels')
    # WIP frag pairs
    psr.add_argument('--resume-frag-pairs',
                     action='store_true',
                     help='resume extraction at frag-pairs')
    # end WIP frag pairs
    psr.set_defaults(func=main)


def extract_features(corpus, output_dir, fix_pseudo_rels, instances,
                     frag_edus=None,
                     vocab_path=None,
                     label_path=None):
    """Extract instances from a corpus, store them in files.

    Run feature extraction for a particular corpus and store the
    results in the output directory. Output file name will be
    computed from the corpus file name.

    Parameters
    ----------
    corpus: filepath
        Path to the corpus.
    output_dir: filepath
        Path to the output folder.
    fix_pseudo_rels: boolean, False by default
        Rewrite pseudo-relations to improve consistency (WIP).
    instances: one of {'same-unit', 'all-pairs'}
        Selection of instances to extract.
    vocab_path: filepath
        Path to a fixed vocabulary mapping, for feature extraction
        (needed if extracting test data: the same vocabulary should be
        used in train and test).
    label_path: filepath
        Path to a list of labels.
    """
    # TODO: perhaps we could just directly invoke the appropriate
    # educe module here instead of going through the command line?
    cmd = [
        "rst-dt-learning", "extract",
        corpus,
        PTB_DIR,  # TODO make this optional and exclusive from CoreNLP
        output_dir,
        '--feature_set', FEATURE_SET,
        '--instances', instances,
    ]
    # NEW 2016-05-19 rewrite pseudo-relations
    if fix_pseudo_rels:
        cmd.extend([
            '--fix_pseudo_rels'
        ])
    # NEW 2016-05-03 use coarse- or fine-grained relation labels
    # NB "coarse" was the previous default
    if LABEL_SET == 'coarse':
        cmd.extend([
            '--coarse'
        ])
    if CORENLP_OUT_DIR is not None:
        cmd.extend([
            '--corenlp_out_dir', CORENLP_OUT_DIR,
        ])
    if LECSIE_DATA_DIR is not None:
        cmd.extend([
            '--lecsie_data_dir', LECSIE_DATA_DIR,
        ])
    if frag_edus is not None:
        cmd.extend(['--frag-edus', frag_edus])
    if vocab_path is not None:
        cmd.extend(['--vocabulary', vocab_path])
    if label_path is not None:
        cmd.extend(['--labels', label_path])
    call(cmd)


def main(args):
    """
    Subcommand main.

    You shouldn't need to call this yourself if you're using
    `config_argparser`
    """
    if args.skip_training or args.resume_frag_pairs:
        tdir = latest_tmp()
    else:
        tdir = current_tmp()

    fix_pseudo_rels = args.fix_pseudo_rels

    # same-unit
    instances = 'same-unit'
    su_prefix_train = '{}.{}'.format(
        instances, os.path.basename(TRAINING_CORPUS))
    su_train_path = os.path.join(tdir, su_prefix_train)
    su_label_path = su_train_path + '.relations.sparse'
    su_vocab_path = su_label_path + '.vocab'
    if TEST_CORPUS is not None:
        su_prefix_test = '{}.{}'.format(
            instances, os.path.basename(TEST_CORPUS))
        su_test_path = os.path.join(tdir, su_prefix_test)

    if SAME_UNIT in ['joint', 'preproc'] and not args.resume_frag_pairs:
        if not args.skip_training:
            # * train
            extract_features(TRAINING_CORPUS, tdir, fix_pseudo_rels,
                             instances)
        if TEST_CORPUS is not None:
            # * test
            extract_features(TEST_CORPUS, tdir, fix_pseudo_rels,
                             instances,
                             vocab_path=su_vocab_path,
                             label_path=su_label_path)

    # all pairs
    instances = 'all-pairs'
    if not args.skip_training and not args.resume_frag_pairs:
        extract_features(TRAINING_CORPUS, tdir, fix_pseudo_rels,
                         instances)
    # path to the vocab and labelset gathered from the training set,
    # we'll use these paths for the test set and for the frag-pairs
    prefix_train = '{}.{}'.format(
        instances, os.path.basename(TRAINING_CORPUS))
    train_path = os.path.join(tdir, prefix_train)
    label_path = train_path + '.relations.sparse'
    vocab_path = label_path + '.vocab'
    if TEST_CORPUS is not None and not args.resume_frag_pairs:
        extract_features(TEST_CORPUS, tdir, fix_pseudo_rels,
                         instances,
                         vocab_path=vocab_path,
                         label_path=label_path)

    # frag pairs: supplementary pairs from/to each fragmented EDU to
    # the other fragmented EDUs and the EDUs that don't belong to any
    # fragmented EDU
    instances = 'frag-pairs'
    # we use the vocabulary and labelset from "all-pairs" ; this is the
    # simplest solution currently and it seems correct, but maybe we
    # could extend "all-pairs" with these pairs when we learn the
    # vocabulary?
    if not args.skip_training:
        frag_edus_train = su_train_path + '.relations' + '.deps_true'
        extract_features(TRAINING_CORPUS, tdir, fix_pseudo_rels,
                         instances, frag_edus=frag_edus_train,
                         vocab_path=vocab_path,
                         label_path=label_path)
    if TEST_CORPUS is not None:
        frag_edus_test = su_test_path + '.relations' + '.deps_true'
        extract_features(TEST_CORPUS, tdir, fix_pseudo_rels,
                         instances, frag_edus=frag_edus_test,
                         vocab_path=vocab_path,
                         label_path=label_path)
    # end frag pairs        

    with open(os.path.join(tdir, "versions-gather.txt"), "w") as stream:
        call(["pip", "freeze"], stdout=stream)

    if not (args.skip_training or args.resume_frag_pairs):
        latest_dir = latest_tmp()
        force_symlink(os.path.basename(tdir), latest_dir)
