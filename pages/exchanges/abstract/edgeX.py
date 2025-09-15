from ccxt.base.types import Entry


class ImplicitAPI:
    # Public GET endpoints
    public_get_metadata = publicGetApiMetadata = Entry('api/v1/public/meta/getMetaData', 'public', 'GET', {'cost': 1})
    public_get_funding = publicGetApiFunding = Entry('api/v1/public/funding/getLatestFundingRate', 'public', 'GET', {'cost': 1})



