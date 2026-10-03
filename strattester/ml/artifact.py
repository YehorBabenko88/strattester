SCHEMA_VERSION = 1

def signal_payload(signal, symbol, model_trained_until):
    return {'schema_version': SCHEMA_VERSION, 'symbol': symbol, 'model_trained_until': int(model_trained_until), 'signal': signal.to_dict()}
