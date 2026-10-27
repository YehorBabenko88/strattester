"""Deterministic bounded Gaussian training; no I/O or implicit checkpoints."""
import math


class TrainingCancelled(RuntimeError):
    pass


def fit_structural(model, features, targets, mask, *, seed=0, steps=20, learning_rate=.001, cancel=lambda:False):
    import torch
    from .financial_contract import integer, finite
    integer(seed,'seed');integer(steps,'steps',1)
    if steps>1000 or not 0<finite(learning_rate,'learning_rate')<=.1: raise ValueError('training resource/config budget')
    if features.ndim!=4 or targets.shape!=(len(features),) or mask.shape!=features.shape[:3] or not len(features):
        raise ValueError('training shapes')
    if len(features)>1024: raise ValueError('training sample budget')
    model.config.validate()
    bank_bytes=sum(t.numel()*t.element_size() for t in (features,targets,mask))
    if bank_bytes>model.config.max_work_bytes:raise ValueError('training bank budget exceeded')
    if cancel():raise TrainingCancelled('training cancelled before state allocation')
    if targets.dtype!=features.dtype or targets.device!=features.device or not torch.isfinite(targets).all(): raise ValueError('invalid labels')
    before={name:value.detach().clone() for name,value in model.state_dict().items()}
    previous_mode=model.training
    deterministic=torch.are_deterministic_algorithms_enabled()
    losses=[]
    try:
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed);torch.use_deterministic_algorithms(True)
            optimizer=torch.optim.Adam(model.parameters(),lr=learning_rate)
            model.train()
            for step in range(steps):
                if cancel():raise TrainingCancelled('training cancelled; state rolled back')
                # Bounded contiguous batches; no implicit mixing of temporal splits.
                begin=(step*model.config.max_batch)%len(features)
                end=min(len(features),begin+model.config.max_batch)
                optimizer.zero_grad(set_to_none=True)
                result=model(features[begin:end],mask[begin:end])
                mu,scale=result.unbind(-1)
                loss=(scale.log()+.5*((targets[begin:end]-mu)/scale).square()+.5*math.log(2*math.pi)).mean()
                if not torch.isfinite(loss):raise ValueError('nonfinite loss')
                loss.backward()
                if not all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters()): raise ValueError('nonfinite gradients')
                torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
                optimizer.step()
                if not all(torch.isfinite(p).all() for p in model.parameters()): raise ValueError('nonfinite updated weights')
                losses.append(float(loss.detach()))
            if cancel():raise TrainingCancelled('training cancelled before completion')
        return tuple(losses)
    except BaseException:
        model.load_state_dict(before)
        raise
    finally:
        model.train(previous_mode)
        torch.use_deterministic_algorithms(deterministic)
