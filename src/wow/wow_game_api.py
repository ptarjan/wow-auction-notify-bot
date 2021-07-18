import logging
from typing import Optional

import requests

from model.auction import Auction
from model.connected_realm import ConnectedRealm
from model.item import Item

TOKEN_URL = 'https://us.battle.net/oauth/token'
DATA_URL = 'https://eu.api.blizzard.com'

PATH_SEARCH_CONNECTED_REALM = '/data/wow/search/connected-realm'
PATH_AUCTION_CONNECTED_REALM = '/data/wow/connected-realm/%d/auctions'
PATH_ITEM = '/data/wow/item/%d'

PARAM_DYNAMIC_NAMESPACE = 'dynamic-eu'
PARAM_STATIC_NAMESPACE = 'static-eu'
PARAM_LOCALE = 'en_US'

logger = logging.getLogger(__name__)


class WowGameApi:

    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token = None

    def connected_realm(self, slug: str) -> Optional[ConnectedRealm]:
        params = {
            'namespace': PARAM_DYNAMIC_NAMESPACE,
            'realms.slug': slug
        }
        headers = {'Authorization': f"Bearer {self._get_access_token()}"}
        response = requests.get(f"{DATA_URL}{PATH_SEARCH_CONNECTED_REALM}", headers=headers, params=params)
        if response.status_code != 200:
            logger.error(f"failed to find connected realm: status={response.status_code}\n{response.text}")
            return None
        results = response.json()['results']
        for result in results:
            data = result['data']
            realm_id = data['id']
            if realm_id:
                name = slug
                for realms in data['realms']:
                    name = realms['name'][PARAM_LOCALE]
                    break
                return ConnectedRealm(realm_id, slug, name)
        logger.info(f"no connected realms found for slug={slug}")
        return None

    def auctions(self, connected_realm_id: int, item_ids: list[int]) -> dict[int, Auction]:
        params = {
            'namespace': PARAM_DYNAMIC_NAMESPACE,
            'locale': PARAM_LOCALE
        }
        headers = {'Authorization': f"Bearer {self._get_access_token()}"}
        response = requests.get(
            f"{DATA_URL}{PATH_AUCTION_CONNECTED_REALM % connected_realm_id}", headers=headers, params=params)
        if response.status_code != 200:
            logger.error(f"failed to fetch auction data for connected_realm_id={connected_realm_id}: "
                         f"status={response.status_code}\n{response.text}")
            return {}
        auctions_data = {}
        auctions = response.json()['auctions']
        for auction in auctions:
            item_id = auction['item']['id']
            if item_id in item_ids:
                qty = auction['quantity']
                price = auction['unit_price'] or auction['buyout']
                item = auctions_data.setdefault(item_id, Auction(item_id))
                item.lots.append(Auction.Lot(price, qty))
        for _, auction in auctions_data.items():
            auction.lots.sort(key=lambda lot: lot.price)
        return auctions_data

    def item_info(self, item_id: int) -> Optional[Item]:
        params = {
            'namespace': PARAM_STATIC_NAMESPACE,
            'locale': PARAM_LOCALE
        }
        headers = {'Authorization': f"Bearer {self._get_access_token()}"}
        response = requests.get(f"{DATA_URL}{PATH_ITEM % item_id}", headers=headers, params=params)
        if response.status_code == 404:
            logger.info(f"item with id={item_id} not found")
            return None
        if response.status_code != 200:
            logger.error(f"failed to fetch item id={item_id} info: "
                         f"status={response.status_code}\n{response.text}")
        name = response.json()['name']
        return Item(item_id, name)

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        response = requests.post(
            TOKEN_URL,
            auth=(self._client_id, self._client_secret),
            data={'grant_type': 'client_credentials'}
        )
        if response.status_code != 200:
            raise ValueError(f"failed to fetch access token:\n{response.text}")
        token = response.json()['access_token']
        if token:
            self._access_token = token
            return self._access_token
        raise ValueError(f"access token not found in response:\n{response.text}")
