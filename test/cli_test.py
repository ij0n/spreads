import time
from itertools import chain, repeat

from mock import patch, MagicMock as Mock
from nose.tools import raises

import spreads
import spreads.cli as cli
import spreads.confit as confit
from spreads.util import DeviceException

spreads.util.find_in_path = Mock(return_value=True)


class TestCLI(object):
    def setUp(self):
        self.workflow = Mock()
        self.workflow.devices = [Mock(), Mock()]
        self.workflow.devices[0].target_page = 'even'
        self.workflow.devices[1].target_page = 'odd'
        self.workflow.capture_start = time.time()
        self.workflow.config = confit.Configuration('test_cli')
        cli.Workflow = Mock(return_value=self.workflow)

    def test_capture(self):
        self.workflow.config['capture']['capture_keys'] = ["b", " "]
        cli.getch = Mock(side_effect=chain(repeat('b', 3), 'c'))
        cli.capture(self.workflow)
        assert cli.getch.call_count == 4
        assert self.workflow.prepare_capture.call_count == 1
        assert self.workflow.capture.call_count == 3
        assert self.workflow.finish_capture.call_count == 1
        #TODO: stats correct?

    @raises(DeviceException)
    def test_capture_nodevices(self):
        cli.getch = Mock(return_value=' ')
        self.workflow.devices = []
        cli.capture(self.workflow)

    @raises(DeviceException)
    def test_capture_no_target_page(self):
        self.workflow.devices[0].target_page = None
        cli.getch = Mock(return_value='c')
        cli.capture(self.workflow)

    def test_postprocess(self):
        self.workflow.path = '/tmp/foo'
        cli.postprocess(self.workflow)
        assert self.workflow.process.call_count == 1

    def test_wizard(self):
        self.workflow.path = '/tmp/foo'
        self.workflow.config['capture']['capture_keys'] = ["b", " "]
        cli.getch = Mock(side_effect=chain(repeat('b', 10), 'c',
                                           repeat('b', 10)))
        cli.wizard(self.workflow)

    def test_parser(self):
        cli.get_pluginmanager = Mock()
        # TODO: Test if plugin arguments are added
        parser = cli.setup_parser()

    @patch('os.path.exists')
    def test_main(self, exists):
        # TODO: Config dumped?
        # TODO: Config from args?
        # TODO: Loglevel set correctly?
        # TODO: Correct function executed?
        self.workflow.config["loglevel"] = "info"
        self.workflow.config["verbose"] = False
        self.workflow.config.dump = Mock()
        cli.confit.LazyConfig = Mock(return_value=self.workflow.config)
        cli.test_cmd = Mock()
        cli.setup_plugin_config = Mock()
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.verbose = False
        mock_args.subcommand = Mock()
        mock_parser.parse_args = Mock(return_value=mock_args)
        cli.setup_parser = Mock(return_value=mock_parser)
        cli.set_config_from_args = Mock()
        exists.return_value = False
        cli.os.path.exists = exists
        cli.main()
        assert mock_args.subcommand.call_count == 1
