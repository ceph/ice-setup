import pytest
from ice_setup import strtobool, prompt, prompt_bool


def true_responses(upper_casing=False):
    if upper_casing:
        return ['Y', 'YES', '']
    return ['y', 'yes', '']


def false_responses(upper_casing=False):
    if upper_casing:
        return ['N', 'NO']
    return ['n', 'no']


def invalid_responses():
    return [9, 0.1, 'h', [], {}, None]


class TestStrToBool(object):

    @pytest.mark.parametrize('response', true_responses())
    def test_trueish(self, response):
        assert strtobool(response) is True

    @pytest.mark.parametrize('response', false_responses())
    def test_falseish(self, response):
        assert strtobool(response) is False

    @pytest.mark.parametrize('response', true_responses(True))
    def test_trueish_upper(self, response):
        assert strtobool(response) is True

    @pytest.mark.parametrize('response', false_responses(True))
    def test_falseish_upper(self, response):
        assert strtobool(response) is False

    @pytest.mark.parametrize('response', invalid_responses())
    def test_invalid(self, response):
        with pytest.raises(ValueError):
            strtobool(response)


class TestPromptBool(object):

    @pytest.mark.parametrize('response', true_responses())
    def test_trueish(self, response):
        fake_input = lambda x: response
        qx = 'what the what?'
        assert prompt_bool(qx, _raw_input=fake_input) is True

    @pytest.mark.parametrize('response', false_responses())
    def test_falseish(self, response):
        fake_input = lambda x: response
        qx = 'what the what?'
        assert prompt_bool(qx, _raw_input=fake_input) is False

    def test_try_again_true(self):
        responses = ['g', 'h', 'y']
        fake_input = lambda x: responses.pop(0)
        qx = 'what the what?'
        assert prompt_bool(qx, _raw_input=fake_input) is True

    def test_try_again_false(self):
        responses = ['g', 'h', 'n']
        fake_input = lambda x: responses.pop(0)
        qx = 'what the what?'
        assert prompt_bool(qx, _raw_input=fake_input) is False


class TestPrompt(object):

    def test_use_default(self):
        fake_input = lambda x: None
        assert prompt('?', default=1, _raw_input=fake_input) == 1

    def test_strip_response(self):
        fake_input = lambda x: ' le whitespace    '
        response = prompt('?', default=1, _raw_input=fake_input)
        assert response == 'le whitespace'

    def test_lowercase_disabled(self):
        fake_input = lambda x: 'HttPs '
        response = prompt('?', _raw_input=fake_input)
        assert response == 'HttPs'

    def test_lowercase_enabled(self):
        fake_input = lambda x: 'HttPs '
        response = prompt('?', lowercase=True, _raw_input=fake_input)
        assert response == 'https'

