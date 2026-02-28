import logging
from gevt.utils import get_set_local_dir
import datetime

local_path = get_set_local_dir('gevt_dir')
now = datetime.datetime.now()
log_path = local_path.joinpath('logging')
if not log_path.exists():
    log_path.mkdir()

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(filename=log_path.joinpath('gevt_{}.log'.format(now.strftime('%Y%m%d_%H_%M_%S'))), level=logging.DEBUG)

