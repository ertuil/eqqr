import json
import logging
from typing import Any, Dict, List, Optional
from email.header import Header
from email.mime.text import MIMEText
from aiosmtplib import SMTP
import config
import httpx
from alibabacloud_dysmsapi20170525.client import Client as Dysmsapi20170525Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dysmsapi20170525 import models as dysmsapi_20170525_models
from alibabacloud_tea_util import models as util_models


class Notifier:
    def __init__(self, name: str = ""):
        self.name = name

    async def emit(
        self, content: str, to: str | List[str], subject: Optional[str] = None
    ):
        pass


class MailNotifier(Notifier):
    def __init__(
        self,
        mail_from: str,
        mail_host: str,
        mail_port: int,
        mail_pass: str,
        mail_tls: bool,
    ):
        super().__init__(name=f"mail-{mail_host}")

        self.mail_from = mail_from
        self.mail_host = mail_host
        self.mail_port = mail_port
        self.mail_pass = mail_pass
        self.mail_tls = mail_tls
        self.logger = logging.getLogger("eqqr.notifier.mail")

    async def emit(
        self, content: str, to: str | List[str], subject: Optional[str] = None
    ):
        if isinstance(to, str):
            mail_to = [to]
        else:
            mail_to = to

        mail_to = [m for m in mail_to if "@" in m]

        if subject is None:
            msg_s = content.split("\n")
            if len(msg_s) <= 0:
                return
            title = msg_s[0]
            title = title[: min(20, len(title))]
            mail_title = title
        else:
            mail_title = subject

        if self.mail_port == 465 or self.mail_tls:
            mail_tls = True
            start_tls = False
        if self.mail_port == 587:
            mail_tls = False
            start_tls = True

        try:
            sender = SMTP(
                hostname=self.mail_host,
                port=self.mail_port,
                use_tls=mail_tls,
                start_tls=start_tls,
            )
            await sender.connect()
            await sender.login(self.mail_from, self.mail_pass)
            if "<body>" in content:
                msg: MIMEText = MIMEText(content, "text/html", "utf-8")
            else:
                msg: MIMEText = MIMEText(content, "plain", "utf-8")
            msg["Subject"] = Header(mail_title, "utf-8")
            msg["From"] = self.mail_from
            msg["To"] = ",".join(mail_to)

            await sender.sendmail(self.mail_from, mail_to, msg.as_string())
            await sender.quit()
            self.logger.info(f"Sent mail to {to} successful")
        except Exception as e:
            self.logger.error(f"Failed to send mail to {to}: {e}")
            return


class PushDeerNotifier(Notifier):
    def __init__(self, server: str = "https://api2.pushdeer.com/"):
        super().__init__(name=f"pushdeer")
        self.server = server
        self.logger = logging.getLogger("eqqr.notifier.pushdeer")

    async def emit(self, content: str, key: str):
        url = f"{self.server}/message/push?pushkey={key}&text={content}"
        with httpx.Client(timeout=5) as client:
            response = client.get(url)
            if response.status_code != 200:
                self.logger.error(f"Failed to send pushdeer message: {response.text}")
            else:
                self.logger.info(f"Sent pushdeer message successful")


class TgNotifier(Notifier):
    def __init__(self, server: str, secret: str, chatid: str):
        super().__init__(name="tg")
        self.tg_server = server
        self.tg_secret = secret
        self.tg_chatid = chatid
        self.logger = logging.getLogger("eqqr.notifier.tg")

    async def emit(self, msg: str, chatid=None):
        if chatid is None:
            chatid = self.tg_chatid
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.tg_secret}",
        }

        data = {"msg": msg}
        if chatid:
            data["chatid"] = chatid

        with httpx.Client(timeout=5) as client:
            response = client.post(self.tg_server, json=data, headers=header)
            if response.status_code != 200:
                self.logger.error(f"Failed to send telegram message: {response.text}")
            else:
                self.logger.info(f"Sent telegram message successful")


class AliSMSNotifier(Notifier):
    def __init__(
        self,
        access_key_id,
        access_key_secret,
        sign_name,
    ):
        super().__init__(name=f"alisms")
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.sign_name = sign_name
        endpoint = f"dysmsapi.aliyuncs.com"

        self.config = open_api_models.Config(
            access_key_id=self.access_key_id, access_key_secret=self.access_key_secret
        )
        self.client = Dysmsapi20170525Client(self.config)
        self.logger = logging.getLogger("eqqr.notifier.alisms")

    async def emit(
        self,
        to: str | List[str],
        template_code: str,
        template_param: Optional[Dict[str, Any]] = None,
    ):
        param_str = template_param
        if isinstance(param_str, dict):
            param_str = json.dumps(param_str)
        if isinstance(to, str):
            to = [to]
        for to_phone in to:
            if "@" in to_phone:
                continue

            if param_str is None:
                send_sms_request = dysmsapi_20170525_models.SendSmsRequest(
                    phone_numbers=to_phone,
                    sign_name=self.sign_name,
                    template_code=template_code,
                )
            else:
                send_sms_request = dysmsapi_20170525_models.SendSmsRequest(
                    phone_numbers=to_phone,
                    sign_name=self.sign_name,
                    template_code=template_code,
                    template_param=param_str,
                )
            try:
                ret = await self.client.send_sms_with_options_async(
                    send_sms_request, util_models.RuntimeOptions()
                )
                self.logger.info(f"send sms successful: {ret}")
            except Exception as error:
                self.logger.error(
                    f"sending sms error: {error.message} {error.data.get('Recommend')}"
                )


mail_notifier = None
pushdeer_notifier = None
tg_notifier = None
alisms_notifier = None


def init_notify():
    global mail_notifier, pushdeer_notifier, tg_notifier, alisms_notifier
    config_notify = config.config.get("notify")
    if config_notify is None:
        return None

    config_smtp = config_notify.get("smtp")
    if config_smtp is not None:
        host = config_smtp.get("host")
        username = config_smtp.get("username")
        if host is not None and username is not None:
            mail_notifier = MailNotifier(
                mail_from=config_smtp.get("username"),
                mail_host=config_smtp.get("host"),
                mail_port=config_smtp.get("port"),
                mail_pass=config_smtp.get("password"),
                mail_tls=config_smtp.get("tls"),
            )

    config_pushdeer = config_notify.get("pushdeer")
    if config_pushdeer is not None:
        server = config_pushdeer.get("server", "https://api2.pushdeer.com/")
        pushdeer_notifier = PushDeerNotifier(server=server)

    config_tg = config_notify.get("tg")
    if config_tg is not None:
        tg_notifier = TgNotifier(
            server=config_tg.get("server"),
            secret=config_tg.get("secret"),
            chatid=config_tg.get("chatid"),
        )

    config_alisms = config_notify.get("alisms")
    if config_alisms is not None:
        access_key_id = config_alisms.get("access_key_id", "")
        access_key_secret = config_alisms.get("access_key_secret", "")
        if access_key_id != "" and access_key_secret != "":
            sign_name = config_alisms.get("sign_name")
            alisms_notifier = AliSMSNotifier(
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                sign_name=sign_name,
            )


if __name__ == "__main__":
    import asyncio

    c = config.get_config("config.yaml")
    init_notify()

    async def main():
        await alisms_notifier.emit(
            "17305690498", "SMS_465374479", template_param={"node": "测试"}
        )

    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
