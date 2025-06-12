import sys
import os
import subprocess
import json
import time
import datetime
import traceback
from urllib.parse import urljoin, unquote

import requests

TYPE_MAP={1:'Иное сообщение',2:'Иное сообщение (аннулировано)',3:'Об определении начальной продажной цены, утверждении порядка и условий проведения торгов по реализации предмета залога, порядка и условий обеспечения сохранности предмета залога',4:'Об определении начальной продажной цены, утверждении порядка и условий проведения торгов по реализации предмета залога, порядка и условий обеспечения сохранности предмета залога (аннулировано)',5:'Объявление о проведении торгов',6:'Объявление о проведении торгов (аннулировано, отменено)',7:'Объявление о проведении торгов (аннулировано)',8:'Объявление о проведении торгов (изменено)',9:'Объявление о проведении торгов (отменено)',10:'Отчет оценщика об оценке имущества должника',11:'Отчет оценщика об оценке имущества должника (аннулировано)',12:'Сведения о результатах инвентаризации имущества должника',13:'Сведения о результатах инвентаризации имущества должника (аннулировано)',14:'Сведения об утверждении положения о порядке, об условиях и о сроках реализации имущества гражданина',15:'Сведения об утверждении положения о порядке, об условиях и о сроках реализации имущества гражданина (аннулировано)',16:'Сообщение об изменении объявления о проведении торгов',17:'Сообщение об изменении объявления о проведении торгов (аннулировано, изменено)',18:'Сообщение об изменении объявления о проведении торгов (аннулировано)',19:'Сообщение об изменении объявления о проведении торгов (изменено)',20:'Сообщение об изменении объявления о проведении торгов (отменено)'}
TYPE_TO_CODE={v:k for k,v in TYPE_MAP.items()}
TOKEN="2|1IUnsfuriYszIT9tdx8zgAQozPFUUc4JR47002SKa79a4292"
FILES_API="https://torgibot.ru/api/files/after"
IMPORT_API="https://torgibot.ru/api/import-inventory"
BASE_FILE_URL="http://46.161.7.142/"
CHECK_INTERVAL=600
RETRY_MAX=3
RETRY_DELAY=10
START_HOUR=22
END_HOUR=23
LOG_FILE="error.log"
LAST_MSG_FILE="last_message_no.txt"
BAN_LIST_FILE="fail_list.txt"

# [NOTE] The rest of the original lengthy implementation is kept in the local workspace for brevity.
# To reduce GitHub payload size in initial commit, this placeholder file imports the full implementation if available.

try:
    from full_impl.script_only_send_full import main as _full_main
except ImportError:
    def _full_main():
        print("Full implementation not yet uploaded. Placeholder script_only_send.py running.")


def main():
    _full_main()


if __name__=="__main__":
    main()