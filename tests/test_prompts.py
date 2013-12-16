import pytest
from setup import strtobool


def true_responses(upper_casing=False):
    if upper_casing:
        return ['Y', 1, '1', 'YES', 'ON', '']
    return ['y', 1, '1', 'yes', 'on', '']


def false_responses(upper_casing=False):
    if upper_casing:
        return ['N', 0, '0', 'NO', 'OFF']
    return ['n', 0, '0', 'no', 'off']


def invalid_responses():
    return [9, 0.1, 'h', [], {}, None]


class TestStrToBool(object):

    @pytest.mark.parametrize('response', true_responses())
    def test_trueish(self, response):
        assert strtobool(response) == 1

    @pytest.mark.parametrize('response', false_responses())
    def test_falseish(self, response):
        assert strtobool(response) == 0

    @pytest.mark.parametrize('response', true_responses(True))
    def test_trueish_upper(self, response):
        assert strtobool(response) == 1

    @pytest.mark.parametrize('response', false_responses(True))
    def test_falseish_upper(self, response):
        assert strtobool(response) == 0

    @pytest.mark.parametrize('response', invalid_responses())
    def test_invalid(self, response):
        with pytest.raises(ValueError):
            strtobool(response)
