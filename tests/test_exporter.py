import http.client
import unittest
from unittest import mock

from opentelemetry import trace as trace_api
from opentelemetry.exporter import jaeger as jaeger_exporter
from opentelemetry.sdk import trace

from splunk_otel.tracing import new_exporter


class TestJaegerExporter(unittest.TestCase):
    def setUp(self):
        self.url = "http://localhost:9080/v1/trace"
        self.service_name = "test-srv"
        context = trace_api.SpanContext(
            trace_id=0x000000000000000000000000DEADBEEF,
            span_id=0x00000000DEADBEF0,
            is_remote=False,
        )

        self._test_span = trace._Span("test_span", context=context)
        self._test_span.start()
        self._test_span.end()

        self.connection_patcher = mock.patch("http.client.HTTPConnection")
        self.connection_mock = self.connection_patcher.start()
        conn = self.connection_mock.return_value
        response = http.client.HTTPResponse(mock.Mock())
        response.status = 200
        conn.getresponse.return_value = response

    def tearDown(self):
        self.connection_patcher.stop()

    def test_exporter_uses_collector_not_udp_agent(self):
        exporter = new_exporter(self.url, self.service_name)

        agent_client_mock = mock.Mock(spec=jaeger_exporter.AgentClientUDP)
        exporter._agent_client = agent_client_mock  # pylint:disable=protected-access
        collector_mock = mock.Mock(spec=jaeger_exporter.Collector)
        exporter._collector = collector_mock  # pylint:disable=protected-access

        exporter.export((self._test_span,))
        self.assertEqual(agent_client_mock.emit.call_count, 0)
        self.assertEqual(collector_mock.submit.call_count, 1)

    def test_http_export(self):
        exporter = new_exporter(self.url, self.service_name)
        exporter.export((self._test_span,))

        conn = self.connection_mock.return_value
        conn.putrequest.assert_called_once_with("POST", "/v1/trace")
        conn.putheader.assert_any_call("User-Agent", "Python/THttpClient (pytest)")
        conn.putheader.assert_any_call("Content-Type", "application/x-thrift")

    def test_http_export_with_authentication(
        self,
    ):
        access_token = "test-access-token"
        exporter = new_exporter(self.url, self.service_name, access_token)
        exporter.export((self._test_span,))

        conn = self.connection_mock.return_value
        conn.putrequest.assert_called_once_with("POST", "/v1/trace")
        conn.putheader.assert_any_call(
            "Authorization", "Basic YXV0aDp0ZXN0LWFjY2Vzcy10b2tlbg=="
        )
        conn.putheader.assert_any_call("User-Agent", "Python/THttpClient (pytest)")
        conn.putheader.assert_any_call("Content-Type", "application/x-thrift")
