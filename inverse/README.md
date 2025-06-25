# Inverse Finance

## FiRM (Fixed Rate Market)

### Data Monitoring

The script `inverse/inverse.py` runs [hourly via GitHub Actions](../.github/workflows/hourly.yml) to monitor key health indicators of the Inverse Finance system using API data.

#### FiRM Monitoring

- **DOLA Supply Check**: Alerts if FiRM's circulating supply exceeds the total DOLA circulating supply by more than 9M DOLA (accounting for Frontier bad debt and Gearbox). Threshold defined [in code](inverse.py#L113).
- **TVL to Borrows Ratio**: Alerts if borrows exceed 80% of the TVL, indicating high utilization. Threshold defined [in code](inverse.py#L116).

#### DOLA Staking Monitoring

- **DOLA Price Stability**: Alerts if DOLA price drops below $0.998, indicating potential depegging. Threshold defined [in code](inverse.py#L123).
- **Staking Coverage**: Alerts if total staked DOLA assets are less than the sDOLA supply, indicating potential undercollateralization. Check defined [in code](inverse.py#L126).
- **Exchange Rate Validation**: Verifies that the calculated exchange rate matches the reported rate from the API. Check defined [in code](inverse.py#L129).

All API responses are validated to ensure data is not older than 2 hours. Timestamp validation logic defined [in code](inverse.py#L39).

#### DOLA Supply Monitoring

DOLA supply is checked from the contract and verified it matches the supply from the API. API data is calculated by summing all values from FED list. If the difference is greater than 0.5%, telegram alert is sent.

#### SDOLA Supply Monitoring

Check SDOLA supply from the contract and verify it matches the supply from the API, if the difference is greater than 0.5%, telegram alert is sent.
