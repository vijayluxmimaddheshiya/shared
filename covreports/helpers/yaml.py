def walk(_dict, keys, _else=None):
    try:
        for key in keys:
            if hasattr(_dict, '_asdict'):
                # namedtuples
                _dict = getattr(_dict, key)
            elif hasattr(_dict, '__getitem__'):
                _dict = _dict[key]
            else:
                _dict = getattr(_dict, key)
        return _dict
    except:
        return _else


def default_if_true(value):
    if value is True:
        yield 'default', {}
    elif type(value) is dict:
        for key, data in value.items():
            if data is False:
                continue
            elif data is True:
                yield key, {}
            elif type(data) is not dict or data.get('enabled') is False:
                continue
            else:
                yield key, data
