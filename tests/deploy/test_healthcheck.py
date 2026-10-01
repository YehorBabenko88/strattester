from strattester.deploy.healthcheck import HealthResult
def test_health_result_is_explicit():
    r=HealthResult(True,'ok'); assert r.ok and r.detail=='ok'
