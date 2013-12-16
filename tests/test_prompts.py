import pytest
from setup import strtobool, prompt


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


class TestPrompt(object):

    @pytest.mark.parametrize('response', true_responses())
    def test_trueish(self, response):
        fake_input = lambda x: response
        qx = 'what the what?'
        assert prompt(qx, _raw_input=fake_input) == 1

    @pytest.mark.parametrize('response', false_responses())
    def test_falseish(self, response):
        fake_input = lambda x: response
        qx = 'what the what?'
        assert prompt(qx, _raw_input=fake_input) == 0

    def test_try_again_true(self):
        responses = ['g', 'h', 1]
        fake_input = lambda x: responses.pop(0)
        qx = 'what the what?'
        assert prompt(qx, _raw_input=fake_input) == 1

    def test_try_again_false(self):
        responses = ['g', 'h', 0]
        fake_input = lambda x: responses.pop(0)
        qx = 'what the what?'
        assert prompt(qx, _raw_input=fake_input) == 0

