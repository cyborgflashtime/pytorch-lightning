import pytest
from pytorch_lightning import Trainer
from pytorch_lightning.examples.new_project_templates.lightning_module_template import LightningTemplateModel
from argparse import Namespace
from test_tube import Experiment
from pytorch_lightning.callbacks import ModelCheckpoint
import numpy as np
import warnings
import torch
import os
import shutil

SEED = 2334
torch.manual_seed(SEED)
np.random.seed(SEED)


# ------------------------------------------------------------------------
# TESTS
# ------------------------------------------------------------------------
def test_cpu_model():
    """
    Make sure model trains on CPU
    :return:
    """
    save_dir = init_save_dir()

    model, hparams = get_model()

    trainer = Trainer(
        progress_bar=False,
        experiment=get_exp(),
        max_nb_epochs=1,
        train_percent_check=0.4,
        val_percent_check=0.4
    )
    result = trainer.fit(model)

    # correct result and ok accuracy
    assert result == 1, 'cpu model failed to complete'
    assert_ok_acc(trainer)

    clear_save_dir()


def test_single_gpu_model():
    """
    Make sure single GPU works (DP mode)
    :return:
    """
    if not torch.cuda.is_available():
        warnings.warn('test_single_gpu_model cannot run. Rerun on a GPU node to run this test')
        return

    trainer_options = dict(
        progress_bar=False,
        max_nb_epochs=1,
        train_percent_check=0.1,
        val_percent_check=0.1,
        gpus=[0]
    )

    run_gpu_model_test(trainer_options)


def test_multi_gpu_model_dp():
    """
    Make sure DP works
    :return:
    """
    if not torch.cuda.is_available():
        warnings.warn('test_multi_gpu_model_dp cannot run. Rerun on a GPU node to run this test')
        return
    if not torch.cuda.device_count() > 1:
        warnings.warn('test_multi_gpu_model_dp cannot run. Rerun on a node with 2+ GPUs to run this test')
        return

    trainer_options = dict(
        progress_bar=False,
        max_nb_epochs=1,
        train_percent_check=0.1,
        val_percent_check=0.1,
        gpus=[0, 1]
    )

    run_gpu_model_test(trainer_options)


def test_amp_gpu_dp():
    """
    Make sure DP + AMP work
    :return:
    """
    if not torch.cuda.is_available():
        warnings.warn('test_amp_gpu_dp cannot run. Rerun on a GPU node to run this test')
        return
    if not torch.cuda.device_count() > 1:
        warnings.warn('test_amp_gpu_dp cannot run. Rerun on a node with 2+ GPUs to run this test')
        return

    trainer_options = dict(
        progress_bar=False,
        max_nb_epochs=1,
        gpus=[0, 1],
        distributed_backend='dp',
        use_amp=True
    )

    run_gpu_model_test(trainer_options)


def test_multi_gpu_model_ddp():
    """
    Make sure DDP works
    :return:
    """
    if not torch.cuda.is_available():
        warnings.warn('test_multi_gpu_model_ddp cannot run. Rerun on a GPU node to run this test')
        return
    if not torch.cuda.device_count() > 1:
        warnings.warn('test_multi_gpu_model_ddp cannot run. Rerun on a node with 2+ GPUs to run this test')
        return

    trainer_options = dict(
        progress_bar=False,
        max_nb_epochs=1,
        train_percent_check=0.1,
        val_percent_check=0.1,
        gpus=[0, 1],
        distributed_backend='ddp'
    )

    run_gpu_model_test(trainer_options)


def test_amp_gpu_ddp():
    """
    Make sure DDP + AMP work
    :return:
    """
    if not torch.cuda.is_available():
        warnings.warn('test_amp_gpu_ddp cannot run. Rerun on a GPU node to run this test')
        return
    if not torch.cuda.device_count() > 1:
        warnings.warn('test_amp_gpu_ddp cannot run. Rerun on a node with 2+ GPUs to run this test')
        return

    trainer_options = dict(
        progress_bar=True,
        max_nb_epochs=1,
        gpus=[0, 1],
        distributed_backend='ddp',
        use_amp=True
    )

    run_gpu_model_test(trainer_options)


# ------------------------------------------------------------------------
# UTILS
# ------------------------------------------------------------------------

def run_gpu_model_test(trainer_options):
    """
        Make sure DDP + AMP work
        :return:
        """
    if not torch.cuda.is_available():
        warnings.warn('test_amp_gpu_ddp cannot run. Rerun on a GPU node to run this test')
        return
    if not torch.cuda.device_count() > 1:
        warnings.warn('test_amp_gpu_ddp cannot run. Rerun on a node with 2+ GPUs to run this test')
        return

    save_dir = init_save_dir()
    model, hparams = get_model()

    # exp file to get meta
    exp = get_exp(False)
    exp.argparse(hparams)
    exp.save()

    # exp file to get weights
    checkpoint = ModelCheckpoint(save_dir)

    # add these to the trainer options
    trainer_options['checkpoint_callback'] = checkpoint
    trainer_options['experiment'] = exp

    # fit model
    trainer = Trainer(**trainer_options)
    result = trainer.fit(model)

    # correct result and ok accuracy
    assert result == 1, 'amp + ddp model failed to complete'

    # test model loading
    pretrained_model = load_model(exp, save_dir)

    # test model preds
    run_prediction(model.test_dataloader, pretrained_model)

    clear_save_dir()


def get_model():
    # set up model with these hyperparams
    root_dir = os.path.dirname(os.path.realpath(__file__))
    hparams = Namespace(**{'drop_prob': 0.2,
                           'batch_size': 32,
                           'in_features': 28*28,
                           'learning_rate': 0.001*8,
                           'optimizer_name': 'adam',
                           'data_root': os.path.join(root_dir, 'mnist'),
                           'out_features': 10,
                           'hidden_dim': 1000})
    model = LightningTemplateModel(hparams)

    return model, hparams


def get_exp(debug=True):
    # set up exp object without actually saving logs
    root_dir = os.path.dirname(os.path.realpath(__file__))
    exp = Experiment(debug=debug, save_dir=root_dir, name='tests_tt_dir')
    return exp


def init_save_dir():
    root_dir = os.path.dirname(os.path.realpath(__file__))
    save_dir = os.path.join(root_dir, 'save_dir')

    if os.path.exists(save_dir):
        shutil.rmtree(save_dir)

    os.makedirs(save_dir, exist_ok=True)

    return save_dir


def clear_save_dir():
    root_dir = os.path.dirname(os.path.realpath(__file__))
    save_dir = os.path.join(root_dir, 'save_dir')
    if os.path.exists(save_dir):
        shutil.rmtree(save_dir)


def load_model(exp, save_dir):

    # load trained model
    tags_path = exp.get_data_path(exp.name, exp.version)
    tags_path = os.path.join(tags_path, 'meta_tags.csv')

    checkpoints = [x for x in os.listdir(save_dir) if '.ckpt' in x]
    weights_dir = os.path.join(save_dir, checkpoints[0])

    trained_model = LightningTemplateModel.load_from_metrics(weights_path=weights_dir, tags_csv=tags_path, on_gpu=True)

    assert trained_model is not None, 'loading model failed'

    return trained_model


def run_prediction(dataloader, trained_model):
    # run prediction on 1 batch
    for batch in dataloader:
        break

    x, y = batch
    x = x.view(x.size(0), -1)

    y_hat = trained_model(x)

    # acc
    labels_hat = torch.argmax(y_hat, dim=1)
    val_acc = torch.sum(y == labels_hat).item() / (len(y) * 1.0)
    val_acc = torch.tensor(val_acc)
    val_acc = val_acc.item()

    print(val_acc)

    assert val_acc > 0.70, f'this model is expected to get > 0.7 in test set (it got {val_acc})'


def assert_ok_acc(trainer):
    # this model should get 0.80+ acc
    acc = trainer.tng_tqdm_dic['val_acc']
    assert acc > 0.70, f'model failed to get expected 0.70 validation accuracy. Got: {acc}'


if __name__ == '__main__':
    pytest.main([__file__])
