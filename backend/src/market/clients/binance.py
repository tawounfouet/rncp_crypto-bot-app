# client_binance.py

import logging
import os

from binance import ThreadedWebsocketManager
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from dotenv import load_dotenv

# Configurer le logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ClientBinance")


class ClientBinance:
    def __init__(self, api_key: str | None = None, api_secret: str | None = None):
        """
        Initialisation du client Binance avec les clés API fournies ou stockées dans .env.
        """
        load_dotenv()
        self.api_key = api_key or os.getenv("BINANCE_TESTNET_API_KEY")
        self.api_secret = api_secret or os.getenv("BINANCE_TESTNET_API_SECRET")

        if not self.api_key or not self.api_secret:
            logger.error("Clés API Binance manquantes")
            raise ValueError("Clés API Binance manquantes dans le fichier .env ou dans les paramètres du client")

        self.client = Client(self.api_key, self.api_secret)
        self._ws_manager = None

    @classmethod
    def from_user_settings(cls, settings):
        """Créer un client Binance à partir des identifiants enregistrés de l'utilisateur."""
        return cls(
            api_key=settings.get_api_key("binance"),
            api_secret=settings.get_api_secret("binance"),
        )

    def _call(self, func, *args, action: str, **kwargs):
        """Exécute un appel au client Binance en centralisant le try/except à 3 niveaux."""
        try:
            return func(*args, **kwargs)
        except BinanceAPIException as e:
            logger.error(f"Erreur API Binance lors de {action}: {e}")
            return None
        except BinanceRequestException as e:
            logger.error(f"Erreur de requête Binance lors de {action}: {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur inattendue lors de {action}: {e}")
            return None

    def get_price(self, symbol: str = "BTCUSDC") -> dict | None:
        """
        Récupère le prix actuel d'un symbole

        Args:
            symbol (str): Paire de trading (ex: BTCUSDC)

        Returns:
            dict: Prix du symbole ou None en cas d'erreur
        """
        return self._call(
            self.client.get_symbol_ticker, symbol=symbol, action=f"récupération du prix (symbol={symbol})"
        )

    def get_historical_klines(self, symbol: str, interval: str, start_str: str) -> list | None:
        """
        Récupère les données historiques de chandeliers (klines)

        Args:
            symbol (str): Paire de trading
            interval (str): Intervalle de temps (ex: Client.KLINE_INTERVAL_1HOUR)
            start_str (str): Date de début (ex: "1 day ago UTC")

        Returns:
            list: Liste des klines ou None en cas d'erreur
        """
        return self._call(
            self.client.get_historical_klines,
            symbol,
            interval,
            start_str,
            action=f"récupération historique (symbol={symbol}, interval={interval})",
        )

    def get_account_balances(self) -> dict[str, float] | None:
        """
        Récupère les soldes positifs du compte

        Returns:
            dict: Dictionnaire {asset: montant} pour les soldes > 0 ou None en cas d'erreur
        """
        account_info = self._call(self.client.get_account, action="récupération portefeuille")
        if account_info is None:
            return None
        try:
            return {b["asset"]: float(b["free"]) for b in account_info["balances"] if float(b["free"]) > 0}
        except Exception as e:
            logger.error(f"Erreur récupération portefeuille: {e}")
            return None

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
    ) -> dict | None:
        """
        Place un ordre sur le marché

        Args:
            symbol (str): Paire de trading
            side (str): Côté de l'ordre (Client.SIDE_BUY ou Client.SIDE_SELL)
            order_type (str): Type d'ordre (Client.ORDER_TYPE_MARKET ou Client.ORDER_TYPE_LIMIT)
            quantity (float): Quantité à acheter/vendre
            price (float, optional): Prix pour les ordres limites

        Returns:
            dict: Réponse de l'API ou None en cas d'erreur
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }

        if order_type == Client.ORDER_TYPE_LIMIT:
            if not price:
                logger.error(f"Prix requis pour les ordres limites (symbol={symbol}, side={side})")
                return None
            params.update({"timeInForce": Client.TIME_IN_FORCE_GTC, "price": str(price)})

        return self._call(
            self.client.create_order,
            **params,
            action=f"création d'ordre (symbol={symbol}, side={side}, type={order_type})",
        )

    def cancel_order(self, symbol: str, order_id: int) -> dict | None:
        """
        Annule un ordre existant

        Args:
            symbol (str): Paire de trading
            order_id (int): ID de l'ordre à annuler

        Returns:
            dict: Réponse de l'API ou None en cas d'erreur
        """
        return self._call(
            self.client.cancel_order,
            symbol=symbol,
            orderId=order_id,
            action=f"annulation d'ordre (symbol={symbol}, order_id={order_id})",
        )

    def get_open_orders(self, symbol: str) -> list[dict] | None:
        """
        Récupère les ordres ouverts pour un symbole

        Args:
            symbol (str): Paire de trading

        Returns:
            list: Liste des ordres ouverts ou None en cas d'erreur
        """
        return self._call(
            self.client.get_open_orders,
            symbol=symbol,
            action=f"récupération des ordres ouverts (symbol={symbol})",
        )

    def get_account_info(self) -> dict | None:
        """
        Récupère les informations du compte

        Returns:
            dict: Informations du compte ou None en cas d'erreur
        """
        return self._call(self.client.get_account, action="récupération des informations du compte")

    def get_asset_balance(self, asset: str) -> dict | None:
        """
        Récupère le solde d'un actif spécifique

        Args:
            asset (str): Symbole de l'actif (ex: BTC)

        Returns:
            dict: Solde de l'actif ou None en cas d'erreur
        """
        return self._call(
            self.client.get_asset_balance,
            asset=asset,
            action=f"récupération du solde de l'actif (asset={asset})",
        )

    def get_exchange_info(self) -> dict | None:
        """
        Récupère les informations de l'échange

        Returns:
            dict: Informations de l'échange ou None en cas d'erreur
        """
        return self._call(self.client.get_exchange_info, action="récupération des informations d'échange")

    def get_server_time(self) -> dict | None:
        """
        Récupère l'heure du serveur Binance

        Returns:
            dict: Heure du serveur ou None en cas d'erreur
        """
        return self._call(self.client.get_server_time, action="récupération de l'heure du serveur")

    def get_symbol_info(self, symbol: str) -> dict | None:
        """
        Récupère les informations d'un symbole

        Args:
            symbol (str): Paire de trading

        Returns:
            dict: Informations du symbole ou None en cas d'erreur
        """
        return self._call(
            self.client.get_symbol_info,
            symbol,
            action=f"récupération des informations du symbole (symbol={symbol})",
        )

    # --- Nouvelles méthodes avancées ---

    def place_stop_loss_order(
        self,
        symbol: str,
        quantity: float,
        stop_price: float,
        limit_price: float | None = None,
    ) -> dict | None:
        """
        Place un ordre stop-loss

        Args:
            symbol (str): Paire de trading
            quantity (float): Quantité à vendre
            stop_price (float): Prix de déclenchement
            limit_price (float, optional): Prix limite si vous utilisez STOP_LOSS_LIMIT

        Returns:
            dict: Réponse de l'API ou None en cas d'erreur
        """
        params = {
            "symbol": symbol,
            "side": Client.SIDE_SELL,
            "quantity": quantity,
            "stopPrice": str(stop_price),
        }

        if limit_price:
            params.update(
                {
                    "type": Client.ORDER_TYPE_STOP_LOSS_LIMIT,
                    "timeInForce": Client.TIME_IN_FORCE_GTC,
                    "price": str(limit_price),
                }
            )
        else:
            params.update({"type": Client.ORDER_TYPE_STOP_LOSS})

        return self._call(
            self.client.create_order,
            **params,
            action=f"création d'ordre stop-loss (symbol={symbol}, stop_price={stop_price})",
        )

    def place_take_profit_order(
        self,
        symbol: str,
        quantity: float,
        stop_price: float,
        limit_price: float | None = None,
    ) -> dict | None:
        """
        Place un ordre take-profit

        Args:
            symbol (str): Paire de trading
            quantity (float): Quantité à vendre
            stop_price (float): Prix de déclenchement
            limit_price (float, optional): Prix limite si vous utilisez TAKE_PROFIT_LIMIT

        Returns:
            dict: Réponse de l'API ou None en cas d'erreur
        """
        params = {
            "symbol": symbol,
            "side": Client.SIDE_SELL,
            "quantity": quantity,
            "stopPrice": str(stop_price),
        }

        if limit_price:
            params.update(
                {
                    "type": Client.ORDER_TYPE_TAKE_PROFIT_LIMIT,
                    "timeInForce": Client.TIME_IN_FORCE_GTC,
                    "price": str(limit_price),
                }
            )
        else:
            params.update({"type": Client.ORDER_TYPE_TAKE_PROFIT})

        return self._call(
            self.client.create_order,
            **params,
            action=f"création d'ordre take-profit (symbol={symbol}, stop_price={stop_price})",
        )

    def place_oco_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        stop_price: float,
        stop_limit_price: float,
    ) -> dict | None:
        """
        Place un ordre OCO (One-Cancels-the-Other)

        Args:
            symbol (str): Paire de trading
            side (str): Côté de l'ordre (Client.SIDE_BUY ou Client.SIDE_SELL)
            quantity (float): Quantité à acheter/vendre
            price (float): Prix limite pour l'ordre limit
            stop_price (float): Prix de déclenchement pour l'ordre stop
            stop_limit_price (float): Prix limite pour l'ordre stop-limit

        Returns:
            dict: Réponse de l'API ou None en cas d'erreur
        """
        return self._call(
            self.client.create_oco_order,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=str(price),
            stopPrice=str(stop_price),
            stopLimitPrice=str(stop_limit_price),
            stopLimitTimeInForce=Client.TIME_IN_FORCE_GTC,
            action=f"création d'ordre OCO (symbol={symbol}, side={side}, price={price}, stop_price={stop_price})",
        )

    def get_order_book(self, symbol: str, limit: int = 100) -> dict | None:
        """
        Récupère le carnet d'ordres d'un symbole

        Args:
            symbol (str): Paire de trading
            limit (int, optional): Nombre d'ordres à récupérer (max 5000)

        Returns:
            dict: Carnet d'ordres ou None en cas d'erreur
        """
        return self._call(
            self.client.get_order_book,
            symbol=symbol,
            limit=limit,
            action=f"récupération du carnet d'ordres (symbol={symbol}, limit={limit})",
        )

    def get_recent_trades(self, symbol: str, limit: int = 500) -> list[dict] | None:
        """
        Récupère les trades récents pour un symbole

        Args:
            symbol (str): Paire de trading
            limit (int, optional): Nombre de trades à récupérer (max 1000)

        Returns:
            list: Liste des trades récents ou None en cas d'erreur
        """
        return self._call(
            self.client.get_recent_trades,
            symbol=symbol,
            limit=limit,
            action=f"récupération des trades récents (symbol={symbol}, limit={limit})",
        )

    def get_historical_trades(self, symbol: str, limit: int = 500, from_id: int | None = None) -> list[dict] | None:
        """
        Récupère les trades historiques pour un symbole

        Args:
            symbol (str): Paire de trading
            limit (int, optional): Nombre de trades à récupérer (max 1000)
            from_id (int, optional): ID à partir duquel récupérer les trades

        Returns:
            list: Liste des trades historiques ou None en cas d'erreur
        """
        params = {"symbol": symbol, "limit": limit}
        if from_id:
            params["fromId"] = from_id
        return self._call(
            self.client.get_historical_trades,
            **params,
            action=f"récupération des trades historiques (symbol={symbol}, limit={limit})",
        )

    def get_aggregate_trades(self, symbol: str, limit: int = 500) -> list[dict] | None:
        """
        Récupère les trades agrégés pour un symbole

        Args:
            symbol (str): Paire de trading
            limit (int, optional): Nombre de trades à récupérer (max 1000)

        Returns:
            list: Liste des trades agrégés ou None en cas d'erreur
        """
        return self._call(
            self.client.get_aggregate_trades,
            symbol=symbol,
            limit=limit,
            action=f"récupération des trades agrégés (symbol={symbol}, limit={limit})",
        )

    def get_all_tickers(self) -> list[dict] | None:
        """
        Récupère les tickers de tous les symboles

        Returns:
            list: Liste des tickers ou None en cas d'erreur
        """
        return self._call(self.client.get_all_tickers, action="récupération de tous les tickers")

    def get_ticker_24h(self, symbol: str | None = None) -> dict | list[dict] | None:
        """
        Récupère les statistiques sur 24h pour un ou tous les symboles

        Args:
            symbol (str, optional): Paire de trading ou None pour tous les symboles

        Returns:
            dict/list: Statistiques sur 24h ou None en cas d'erreur
        """
        action = f"récupération du ticker 24h (symbol={symbol if symbol else 'all'})"
        if symbol:
            return self._call(self.client.get_ticker, symbol=symbol, action=action)
        return self._call(self.client.get_ticker, action=action)

    # --- WebSocket API ---

    def _init_websocket(self) -> None:
        """Initialise le gestionnaire de WebSockets s'il n'existe pas déjà"""
        if not self._ws_manager:
            self._ws_manager = ThreadedWebsocketManager(api_key=self.api_key, api_secret=self.api_secret)
            self._ws_manager.start()
            logger.info("WebSocket manager initié")

    def start_kline_socket(self, symbol: str, interval: str, callback) -> str | None:
        """
        Démarre un socket pour recevoir les données de klines en temps réel

        Args:
            symbol (str): Paire de trading
            interval (str): Intervalle de temps (ex: Client.KLINE_INTERVAL_1MINUTE)
            callback (function): Fonction de callback à appeler quand des données sont reçues

        Returns:
            str: Clé de connexion ou None en cas d'erreur
        """
        try:
            self._init_websocket()
            return self._ws_manager.start_kline_socket(callback=callback, symbol=symbol, interval=interval)
        except Exception as e:
            logger.error(f"Erreur démarrage du socket kline: {e} (symbol={symbol}, interval={interval})")
            return None

    def start_symbol_ticker_socket(self, symbol: str, callback) -> str | None:
        """
        Démarre un socket pour recevoir les mises à jour des tickers

        Args:
            symbol (str): Paire de trading
            callback (function): Fonction de callback à appeler quand des données sont reçues

        Returns:
            str: Clé de connexion ou None en cas d'erreur
        """
        try:
            self._init_websocket()
            return self._ws_manager.start_symbol_ticker_socket(callback=callback, symbol=symbol)
        except Exception as e:
            logger.error(f"Erreur démarrage du socket ticker: {e} (symbol={symbol})")
            return None

    def start_depth_socket(self, symbol: str, callback, depth: str = "5") -> str | None:
        """
        Démarre un socket pour recevoir les mises à jour du carnet d'ordres

        Args:
            symbol (str): Paire de trading
            callback (function): Fonction de callback à appeler quand des données sont reçues
            depth (str, optional): Profondeur du carnet ("5", "10", "20")

        Returns:
            str: Clé de connexion ou None en cas d'erreur
        """
        try:
            self._init_websocket()
            return self._ws_manager.start_depth_socket(callback=callback, symbol=symbol, depth=depth)
        except Exception as e:
            logger.error(f"Erreur démarrage du socket depth: {e} (symbol={symbol}, depth={depth})")
            return None

    def stop_socket(self, conn_key: str) -> None:
        """
        Arrête un socket spécifique

        Args:
            conn_key (str): Clé de connexion du socket à arrêter
        """
        if self._ws_manager:
            try:
                self._ws_manager.stop_socket(conn_key)
                logger.info(f"Socket arrêté (conn_key={conn_key})")
            except Exception as e:
                logger.error(f"Erreur arrêt du socket: {e} (conn_key={conn_key})")

    def stop_all_sockets(self) -> None:
        """Arrête tous les sockets et détruit le gestionnaire de WebSockets"""
        if self._ws_manager:
            try:
                self._ws_manager.stop()
                self._ws_manager = None
                logger.info("Tous les sockets ont été arrêtés")
            except Exception as e:
                logger.error(f"Erreur arrêt de tous les sockets: {e}")


# Test de la classe ClientBinance
if __name__ == "__main__":
    client = ClientBinance()

    # Account Info
    account_info = client.get_account_info()
    if account_info:
        print(f"Compte utilisateur - Status: {account_info.get('accountType', 'N/A')}")

        # Afficher quelques actifs disponibles avec solde non-nul
        balances = client.get_account_balances()
        if balances:
            print("\nSoldes disponibles:")
            for asset, amount in balances.items():
                print(f"{asset}: {amount}")

    # Prix actuel du BTC
    btc_price = client.get_price("BTCUSDC")
    if btc_price:
        print(f"\nPrix actuel du BTC: {btc_price['price']} USDC")

    # Exemple de données de marché
    order_book = client.get_order_book("BTCUSDC", limit=5)
    if order_book:
        print("\nCarnet d'ordres (5 premiers):")
        print("Achats:", order_book["bids"][:3])
        print("Ventes:", order_book["asks"][:3])

    # Statistiques sur 24h
    stats_24h = client.get_ticker_24h("BTCUSDC")
    if stats_24h:
        print(f"\nStatistiques 24h - Volume BTC: {stats_24h['volume']} - Variation: {stats_24h['priceChangePercent']}%")
