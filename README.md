# Monitoring Scripts

This repository contains scripts for monitoring various DeFi protocols.

## Bad Debt Alert

Alerting Telegram bot for bad debt data from Risk DAO. It's a simple Python script that is triggered by GitHub actions every hour. It checks bad debt data for a given protocol and if the value is above a given threshold it will send Telegram message to a defined chat.

Currently tracked protocols are: Aave V3, Compound and Maker DAO. For more info check workflow files in `.github/workflows`.

### Add new alert

- Add new workflow to `.github/workflows`
- In GitHub repository settings add [secrets](.github/workflows/sonne-bad-debt.yml#L23):
    - [`BAD_DEBT_TELEGRAM_TOKEN`](https://core.telegram.org/bots/tutorial#obtain-your-bot-token) - generate token for your bot.
    - [`BAD_DEBT_TELEGRAM_CHAT_ID`](https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates) - open the link in a browser and change `{TELEGRAM_TOKEN}` to your token. Find your chat id in the JSON response. It's possible to set multiple chat ids separated by comma.
- Set remaining [env variables](.github/workflows/bad-debt-alert.yml#L25):
    - `PROTOCOL` name of the protocol you want to monitor.
    - `DEBT_THRESHOLD` in dollars after which an alert will be sent to Telegram chat. Optional value.
    - `DEBT_THRESHOLD_RATIO` in percent after which an alert will be sent to Telegram chat. Default value is 100%.
    - `DATA_URL` link to the data source in JSON format. [Link](https://github.com/Risk-DAO/simulation-results/tree/main/bad-debt/latest) to all RiskDAO data sources. Example data URL for [Sonne Finance](https://raw.githubusercontent.com/Risk-DAO/simulation-results/main/bad-debt/latest/optimism_sonne.json).
