from django.test import RequestFactory, Client, TestCase
import os
from django.http import HttpResponseRedirect
from django.db import Error
import pytest
import logging
import json
from django.contrib.auth.models import User, AnonymousUser
from swirl.models import Search, Result
from swirl.authenticators.microsoft import Microsoft
from swirl.authenticators.authenticator import Authenticator
from swirl.connectors.microsoft_graph import MicrosoftTeams, M365OutlookMessages
from django.conf import settings
from swirl.search import search as search_exec
from swirl.serializers import ResultSerializer, SearchProviderSerializer
import random
import string
import responses

@pytest.fixture
def test_suser_pw():
    return 'password'

@pytest.fixture
def test_suser(test_suser_pw):
    return User.objects.create_user(
        username=''.join(random.choices(string.ascii_uppercase + string.digits, k=10)),
        password=test_suser_pw,
        is_staff=True,  # Set to True if your view requires a staff user
        is_superuser=True,  # Set to True if your view requires a superuser
    )

@pytest.fixture
def test_suser_anonymous():
    return AnonymousUser()

@pytest.fixture
def session():
    a = Microsoft()
    return {
        a.access_token_field: 'access_token',
        a.refresh_token_field: 'refresh_token',
        a.expires_in_field: 99999999999999
    }

@pytest.fixture
def _request(test_suser, session):
    r = RequestFactory()
    r.user = test_suser
    r.session = {
        'user': session
    }
    return r

@pytest.fixture
def _anonymous_request(test_suser_anonymous, session):
    r = RequestFactory()
    r.user = test_suser_anonymous
    return r

@pytest.fixture
def app():
    return Microsoft()

@pytest.fixture
def client():
    return Client()

@pytest.fixture
def request_api_url():
    return 'https://xxx.mockable.io/rest/v2/plus/search/dc/?q=facebook'

logger = logging.getLogger(__name__)


class GeneralRequestAPITestCase(TestCase):

    @pytest.fixture(autouse=True)
    def _init_fixtures(self, client, _request, _anonymous_request, test_suser, test_suser_pw, test_suser_anonymous, app, request_api_url):
        self._client = client
        self._request = _request
        self._anonymous_request = _anonymous_request
        self._test_suser = test_suser
        self._test_suser_pw = test_suser_pw
        self._test_suser_anonymous = test_suser_anonymous
        self._app = app
        self._request_api_url = request_api_url

    def setUp(self):
        settings.CELERY_TASK_ALWAYS_EAGER = True

    def tearDown(self):
        settings.CELERY_TASK_ALWAYS_EAGER = False

    def _get_connector_name(self):
        return ''

    def _get_provider_data(self):
        return {}

    def _get_hits(self):
        return []

    def _mock_response(self):
        return {
            'value': [
                {
                    'hitsContainers': [
                        {
                            'hits': self._get_hits()
                        }
                    ]
                }
            ]
        }

    def _create_provider(self):
        provider = self._get_provider_data()
        serializer = SearchProviderSerializer(data=provider)
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=self._test_suser)
        provider_id = serializer.data['id']
        return provider_id

    def _create_search(self):
        provider_id = self._create_provider()
        try:
            new_search = Search.objects.create(query_string='test',searchprovider_list=[provider_id],owner=self._test_suser)
        except Error as err:
            assert f'Search.create() failed: {err}'
        new_search.status = 'NEW_SEARCH'
        new_search.save()
        return new_search.id

    def _run_search(self):
        search_id = self._create_search()
        result = search_exec(search_id, Authenticator().get_session_data(self._request))
        assert result is True
        assert self._check_result(search_id) is True

    def _check_result(self, search_id):
        return True

    @responses.activate
    def test_request_api(self):
        ### CHECKING FOR PARENT CLASS
        if self._get_connector_name() == '':
            return
        responses.add(responses.GET, self._request_api_url, body=json.dumps(self._mock_response()).encode('utf-8'), status=200)
        result = self._run_search()


class LibraryDatasourceTest(GeneralRequestAPITestCase):

    def _get_connector_name(self):
        return 'M365OutlookMessages'

    def _get_provider_data(self):

        return {
                    "name": "Library Mock (web/Library)",
                    "shared": True,
                    "active": True,
                    "default": True,
                    "connector": "RequestsGet",
                    "url": "https://xxx.mockable.io/rest/v2/plus/search/dc/",
                    "query_template": "{url}?q={query_string}",
                    "post_query_template": "{}",
                    "query_processors": [
                    "AdaptiveQueryProcessor"
                    ],
                    "query_mappings": "",
                    "result_grouping_field": "",
                    "result_processors": [
                    "MappingResultProcessor"
                    ],
                    "response_mappings": "FOUND=info.total,RESULTS=docs",
                    "result_mappings": "date_published_display=pnx.display.creationdate[0],title=pnx.display.title[0],body=pnx.display.description[0],date_published=pnx.sort.creationdate[0],author=pnx.sort.author[0],url='https://xxx.place.edu/primo-explore/fulldisplay?docid={pnx.control.recordid[0]}&context=L&vid=XXX2',pnx.facets.creatorcontrib[*],pnx.display.publisher[*],pnx.display.edition[*],pnx.display.format[*],pnx.display.language[*],pnx.enrichment.classificationlcc[*],NO_PAYLOAD",
                    "results_per_query": 10,
                    "credentials": "",
                    "eval_credentials": "",
                    "tags": []
            }

    def _create_search(self):
        provider_id = self._create_provider()
        try:
            new_search = Search.objects.create(query_string='facebook',searchprovider_list=[provider_id],owner=self._test_suser)
        except Error as err:
            assert f'Search.create() failed: {err}'
        new_search.status = 'NEW_SEARCH'
        new_search.save()
        return new_search.id

    def _get_hits(self):
        data_dir = os.path.dirname(os.path.abspath(__file__))
        # Build the absolute file path for the JSON file in the 'data' subdirectory
        json_file_path = os.path.join(data_dir, 'data', 'libsystem_message_results.json')

        # Read the JSON file
        with open(json_file_path, 'r') as file:
            data = json.load(file)
        return data

    def _check_result(self, search_id):
        result_count = Result.objects.filter(search_id=search_id).count()
        assert result_count == 1
        rs = Result.objects.get(search_id=search_id)
        jsr = rs.json_results
        assert jsr
        assert len(jsr) == 1
        hits = self._get_hits()
        assert jsr[0].get('title') == '<em>Facebook</em> :The Missing Manual'
        assert jsr[0].get('body') == "<em>Facebook</em> is the wildly popular, free social networking site that combines the best of blogs, online forums and groups, photosharing, clever applications, and interaction among friends. The one thing it doesn't have is a users guide to help you truly take advantage of it. Until now. <em>Facebook</em>: The Missing Manual gives you a very objective and entertaining look at everything this fascinating <em>Facebook</em> phenomenon has to offer. Teeming with high-quality color graphics, each page in this guide is uniquely designed to help you with specific <em>Facebook</em> tasks, such as signing up,"
        assert jsr[0].get('url') == "https://xxx.place.edu/primo-explore/fulldisplay?docid=[]&context=L&vid=XXX2"
        assert jsr[0].get('date_published_display') == '2008'
        assert jsr[0].get('date_published') == '2008-01-01 00:00:00'

        return True

    def _mock_response(self):
        return self._get_hits()