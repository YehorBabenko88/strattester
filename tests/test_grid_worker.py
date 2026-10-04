import json
from strattester.grid_bridge import digest,validate_manifest
from strattester.grid_worker import main


def test_grid_worker_probe_produces_valid_manifest(tmp_path):
    config={"mode":"test"}; spec={"hello":"world"}
    payload={
        "research_run_id":"run-1","research_shard_id":"shard-1",
        "job_type":"probe","dataset_hash":"dataset-1",
        "strattester_version":"commit-1","config":config,
        "config_hash":digest(config),"input_spec":spec,"input_hash":digest(spec),
    }
    job=tmp_path/"job.json"; out=tmp_path/"result.json"
    job.write_text(json.dumps({"payload":payload}),encoding="utf-8")
    assert main(["--job",str(job),"--output",str(out)])==0
    manifest=json.loads(out.read_text(encoding="utf-8"))
    assert validate_manifest(manifest,{
        "run_id":"run-1","job_id":"shard-1","job_type":"probe",
        "dataset_hash":"dataset-1","code_version":"commit-1",
        "config_hash":digest(config),"input_hash":digest(spec),
    })
    assert manifest["result"]["probe"]==spec


def test_grid_worker_rejects_mutated_input_before_execution(tmp_path):
    config={}; spec={"x":1}
    payload={
        "research_run_id":"r","research_shard_id":"s","job_type":"probe",
        "dataset_hash":"d","strattester_version":"c","config":config,
        "config_hash":digest(config),"input_spec":{"x":2},"input_hash":digest(spec),
    }
    job=tmp_path/"job.json"; out=tmp_path/"out.json"
    job.write_text(json.dumps(payload),encoding="utf-8")
    try:
        main(["--job",str(job),"--output",str(out)])
    except SystemExit as exc:
        assert "input hash mismatch" in str(exc)
    else:
        raise AssertionError("mutated input was accepted")
