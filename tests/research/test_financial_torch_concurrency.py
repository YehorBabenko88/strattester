"""Owned CPU workers only; no GPU/native sandbox execution."""
from concurrent.futures import ThreadPoolExecutor
import threading
import pytest
import torch
from strattester.research.financial_structural_model import StructuralConfig,build_structural_model
from strattester.research.financial_training import fit_structural
from pathlib import Path
import runpy


def data():
    return torch.ones(1,1,3,3),torch.tensor([.01]),torch.ones(1,1,3,dtype=torch.bool)


@pytest.mark.parametrize('other',['training','checkpoint'])
def test_concurrent_training_does_not_overlap_process_rng_windows(monkeypatch,tmp_path,other):
    cfg=StructuralConfig(recycles=0)
    a,b=build_structural_model(cfg),build_structural_model(cfg)
    # Warm the real optimizer imports before scheduling the interleaving.
    fit_structural(build_structural_model(cfg),*data(),steps=1)
    first=threading.Event();second=threading.Event();release=threading.Event();started=threading.Event()
    forward_a=a.forward;forward_b=b.forward
    def fa(*args):
        first.set();assert release.wait(10)
        return forward_a(*args)
    def fb(*args):
        second.set();return forward_b(*args)
    monkeypatch.setattr(a,'forward',fa);monkeypatch.setattr(b,'forward',fb)
    import strattester.research.financial_checkpoint as checkpoints
    if other=='checkpoint':
        path=tmp_path/'model.json'
        pin=checkpoints.save_checkpoint(b,path,dataset_sha256='a'*64,seed=22)
        construct=checkpoints.build_structural_model
        def observed(*args,**kwargs):
            second.set();return construct(*args,**kwargs)
        monkeypatch.setattr(checkpoints,'build_structural_model',observed)
    torch.manual_seed(818)
    before=torch.random.get_rng_state().clone()
    deterministic=torch.are_deterministic_algorithms_enabled()
    def worker_b():
        started.set()
        return checkpoints.load_checkpoint(path,pin) if other=='checkpoint' else fit_structural(b,*data(),seed=22,steps=1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        left=pool.submit(fit_structural,a,*data(),seed=11,steps=1)
        try:
            assert first.wait(10)
            right=pool.submit(worker_b)
            assert started.wait(10)
            overlapped=second.wait(.3)
        finally:release.set()
        assert left.result(timeout=15)
        assert right.result(timeout=15)
    assert not overlapped,'training entered another thread RNG/determinism window'
    assert torch.equal(before,torch.random.get_rng_state())
    assert torch.are_deterministic_algorithms_enabled()==deterministic


def test_experiment_does_not_reseed_the_callers_cpu_rng(tmp_path):
    from strattester.research.financial_experiment import run_experiment
    examples=runpy.run_path(str(Path(__file__).with_name('test_financial_experiment.py')))['examples']()
    torch.manual_seed(912)
    before=torch.random.get_rng_state().clone()
    run_experiment(examples,tmp_path/'checkpoint.json',train_end=1200,validation_end=2400,test_end=3400,
        holdout_symbols={'ETHUSDT'},config=StructuralConfig(recycles=0),steps=1,seed=7)
    assert torch.equal(before,torch.random.get_rng_state())


def test_waiting_research_job_can_cancel_without_entering_training():
    from strattester.research.financial_torch_runtime import cpu_research_slot
    from strattester.research.financial_training import TrainingCancelled
    checked=threading.Event();cancel=threading.Event()
    def cancelled():checked.set();return cancel.is_set()
    model=build_structural_model(StructuralConfig(recycles=0))
    with ThreadPoolExecutor(max_workers=1) as pool:
        with cpu_research_slot():
            future=pool.submit(fit_structural,model,*data(),steps=1,cancel=cancelled)
            assert checked.wait(5)
            cancel.set()
            with pytest.raises(TrainingCancelled,match='waiting'):future.result(timeout=5)
    # A cancelled waiter neither leaks the slot nor blocks subsequent work.
    assert fit_structural(model,*data(),steps=1)


def test_slot_wait_has_a_bounded_admission_timeout(monkeypatch):
    import strattester.research.financial_torch_runtime as runtime
    monkeypatch.setattr(runtime,'_MAX_WAIT_SECONDS',.1)
    def enter():
        with runtime.cpu_research_slot():raise AssertionError('busy slot entered')
    with ThreadPoolExecutor(max_workers=1) as pool:
        with runtime.cpu_research_slot():
            future=pool.submit(enter)
            with pytest.raises(ValueError,match='admission timeout'):future.result(timeout=5)


def test_cpu_state_exception_restores_rng_and_warn_only_without_cuda(monkeypatch):
    from strattester.research.financial_torch_runtime import cpu_research_state
    def deny(*args,**kwargs):raise AssertionError('CPU path must not seed CUDA')
    monkeypatch.setattr(torch.cuda,'manual_seed_all',deny)
    before=torch.random.get_rng_state().clone()
    enabled=torch.are_deterministic_algorithms_enabled()
    warn=torch.is_deterministic_algorithms_warn_only_enabled()
    try:
        torch.use_deterministic_algorithms(True,warn_only=True)
        with pytest.raises(RuntimeError,match='owned failure'):
            with cpu_research_state(seed=31,deterministic=True):
                assert not torch.is_deterministic_algorithms_warn_only_enabled()
                raise RuntimeError('owned failure')
        assert torch.equal(before,torch.random.get_rng_state())
        assert torch.are_deterministic_algorithms_enabled()
        assert torch.is_deterministic_algorithms_warn_only_enabled()
    finally:torch.use_deterministic_algorithms(enabled,warn_only=warn)


def test_parallel_seeded_models_match_sequential_fingerprints():
    from strattester.research.financial_checkpoint import model_fingerprint
    cfg=StructuralConfig(recycles=0)
    seeds=[11,22,11,33]
    def construct(seed):return model_fingerprint(build_structural_model(cfg,seed=seed))
    expected=[construct(seed) for seed in seeds]
    before=torch.random.get_rng_state().clone()
    with ThreadPoolExecutor(max_workers=4) as pool:actual=list(pool.map(construct,seeds))
    assert actual==expected
    assert torch.equal(before,torch.random.get_rng_state())


def test_parallel_training_matches_sequential_losses_and_weights():
    from strattester.research.financial_checkpoint import model_fingerprint
    cfg=StructuralConfig(recycles=0)
    def train(seed):
        model=build_structural_model(cfg,seed=seed)
        losses=fit_structural(model,*data(),seed=seed,steps=2)
        return losses,model_fingerprint(model)
    seeds=[11,22,11]
    expected=[train(seed) for seed in seeds]
    before=torch.random.get_rng_state().clone()
    with ThreadPoolExecutor(max_workers=3) as pool:actual=list(pool.map(train,seeds))
    assert actual==expected
    assert torch.equal(before,torch.random.get_rng_state())


def test_mid_fit_cancellation_rolls_back_and_releases_cpu_slot(monkeypatch):
    from strattester.research.financial_training import TrainingCancelled
    model=build_structural_model(StructuralConfig(recycles=0),seed=19)
    original={k:v.clone() for k,v in model.state_dict().items()}
    before=torch.random.get_rng_state().clone();cancelled=threading.Event();forward=model.forward
    def forward_then_cancel(*args):
        result=forward(*args);cancelled.set();return result
    monkeypatch.setattr(model,'forward',forward_then_cancel)
    with pytest.raises(TrainingCancelled):fit_structural(model,*data(),steps=2,cancel=cancelled.is_set)
    assert all(torch.equal(original[k],v) for k,v in model.state_dict().items())
    assert torch.equal(before,torch.random.get_rng_state())
    monkeypatch.setattr(model,'forward',forward)
    assert fit_structural(model,*data(),steps=1)
