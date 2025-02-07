import os
import sys
import json
import requests
import asyncio
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey # type: ignore
from solana.exceptions import SolanaRpcException
from solders.signature import Signature #type: ignore
import httpx, httpcore
import asyncpg
import random, string
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from logger import error, info, warn
from sklearn.metrics import classification_report, roc_auc_score
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.metrics import classification_report, roc_auc_score, make_scorer

class BotMain:
    def __init__(self):
        try:
            self.config = self.load_config()
            self.solana_client = AsyncClient(self.config['rpc'])
            self.rpc_url = self.config['rpc']
            self.webhooks = self.config['webhooks']
            self.addy_pf_bonding_curve = "39azUYFWPz3VHgKCf3VChUwbpURdCHRxjWVowf5jUJjg"
            self.helius_apikey = self.config['helius_apikey']
            self.birdeye_apikey = self.config['birdeye_apikey']
        except Exception as e:
            error(f"Error initializing BotMain: {e}")

    def load_config(self):
        try:
            config_path = 'config.json'
            if os.path.exists(config_path):
                with open(config_path, 'r') as config_file:
                    return json.load(config_file)
            else:
                error(f"Config file {config_path} not found.")
                sys.exit(1)
        except Exception as e:
            error(f"Error loading config: {e}")
            sys.exit(1)

    async def run(self, class_b_instance):
        try:
            self.class_b_instance = class_b_instance
            warn("Bot is starting...")
            await self.monitor_new_signatures()
        except Exception as e:
            error(f"Error running bot: {e}")


    async def monitor_new_signatures(self):
        try:
            signature = None
            backoff_delay = 2
            max_backoff = 60
            url =f"https://mainnet.helius-rpc.com/?api-key={self.helius_apikey}"

            while True:
                try:
                    response = requests.post(
                        url,
                        headers={"Content-Type":"application/json"},
                        json={"jsonrpc":"2.0","id":"1","method":"getSignaturesForAddress","params":[self.addy_pf_bonding_curve,{"limit":1}]}
                    )
                    
                except SolanaRpcException as ex:
                    if ex.__cause__ and isinstance(ex.__cause__, httpx.HTTPStatusError):
                        if ex.__cause__.response.status_code == 429:
                            warn(
                                f"Got 429 Too Many Requests, backing off for {backoff_delay} seconds..."
                            )
                            await asyncio.sleep(backoff_delay)
                            backoff_delay = min(backoff_delay * 2, max_backoff)
                            continue
                    raise

                except httpcore.ReadTimeout:
                    warn(
                        f"Got ReadTimeout, backing off for {backoff_delay} seconds..."
                    )
                    await asyncio.sleep(backoff_delay)
                    backoff_delay = min(backoff_delay * 2, max_backoff)
                    continue
 
                backoff_delay = 2
                response = response.json()
                if response["result"]:
                    new_signature = response["result"][0]["signature"]
                    if signature != new_signature:
                        signature = new_signature
                        info(f"New Signature Found: {signature}")
                        task_number = random.randint(10000, 99999)
                        warn(f"Creating task {task_number} for signature: {signature}")
                        asyncio.create_task(self.handle_new_signature(signature, task_number))
                    else:
                        warn("Monitoring new signatures...")
                else:
                    warn(response.json())
                    await asyncio.sleep(5)
                await asyncio.sleep(2)

        except Exception as e:
            error(f"Error monitoring new signatures - {e}")

    async def handle_new_signature(self, signature, task_number):
        coin = {}
        self.newcoin = ""
        signature = Signature.from_string(signature)
        try:
            warn(f"{task_number} - Handling new signature in a separate thread: {signature}")
            response = await self.solana_client.get_transaction(signature, encoding="json", max_supported_transaction_version=0)
            if response.value and response.value.transaction.meta.pre_token_balances:
                token_address = response.value.transaction.meta.pre_token_balances[0].mint
                if token_address == self.newcoin:
                    warn(f"{task_number} - Token already in database")
                if "pump" in str(token_address):
                    info(f"{task_number} - New token found: {token_address}")
                    self.newcoin = token_address
                    coin['token_address'] = response.value.transaction.meta.pre_token_balances[0].mint
                    await self.get_token_name(task_number, coin)
                else:
                    warn(f"{task_number} - Token not found: {token_address}")
            else:
                error(f"{task_number} - No token found in the transaction metadata.")
        except Exception as e:
            error(f"{task_number} - Invalid signature: {e}")
            warn(response)

    async def get_token_name(self,task_number, coin):
        coin["website_check"] = False
        coin["twitter_check"] = False
        coin["telegram_check"] = False
        url = "https://public-api.birdeye.so/defi/token_overview?address={}".format(str(coin['token_address']))
        headers = {
            "accept": "application/json; charset=utf-8",
            "x-chain": "solana",
            "X-API-KEY": self.birdeye_apikey
        }
        try:
            while True:
                info(f"{task_number} - Getting token info")
                async with httpx.AsyncClient() as client:
                    try:
                        response = await client.get(url=url, headers=headers, timeout=15)
                        try:
                            data = json.loads(response.content.decode("utf-8",errors="replace"))
                        except json.JSONDecodeError as e:
                            error(f"JSON decoding error: {e}")
                            await asyncio.sleep(15)
                        if response.status_code == 500:
                            error(f"{task_number} - Internal server error")
                            await asyncio.sleep(5)
                        if response.status_code != 200:
                            error(f"{task_number} - Error getting token info: {response.status_code}")
                            await asyncio.sleep(5)
                        else:
                            if data['data']:
                                if data['data']['extensions']:
                                    if 'twitter' in data['data']['extensions']:
                                        coin["twitter"] = data['data']['extensions']["twitter"]
                                        coin["twitter_check"] = True
                                    if 'telegram' in data['data']['extensions']:
                                        coin["telegram"] = data['data']['extensions']["telegram"]
                                        coin["telegram_check"] = True
                                    if 'website' in data['data']['extensions']:
                                        coin["website_check"] = True
                                        coin["website"] = data['data']['extensions']["website"]
                                try:
                                    coin["token_name"] = str(data['data']["symbol"])
                                except:
                                    coin["token_name"] = "Unknown"
                                try:
                                    coin["token_img"] = data['data']["logoURI"]
                                except:
                                    coin["token_img"] = "https://cdn.discordapp.com/attachments/807532576771145749/1331994599438417992/Politics_Inaug_Elon_GettyImages-2194418262.webp?ex=6793a423&is=679252a3&hm=1458ee844cb40326f0d88bc9496019400f01d14fa3bdb06f0305f8acdf159d22&"
                                info(f"{task_number} - Token Name: {coin['token_name']}")
                                break
                            else:                              
                                break
                    except (httpx.RequestError, httpx.TimeoutException, Exception) as e:
                        error(f"{task_number} - Request error: {e}. Retrying...")
                        warn(Exception)
                        await asyncio.sleep(5)  # Wait for 3 seconds before retrying
            try:
                if coin['token_name']:
                    await self.get_creator_wallet(task_number,coin)
            except:
                error(f"{task_number} - No data found for token, skipping.")
                pass

        except Exception as e:
            error(f"{task_number} - Error getting token info: {e}")

    async def get_creator_wallet(self,task_number, coin):
        url = "https://public-api.birdeye.so/defi/token_creation_info?address={}".format(str(coin['token_address']))
        headers = {
            "accept": "application/json",
            "x-chain": "solana",
            "X-API-KEY": self.birdeye_apikey
        }
        counter = 0
        try:
            while True:
                info(f"{task_number} - Getting creator wallet")
                async with httpx.AsyncClient() as client:
                    response = await client.get(url=url, headers=headers, timeout=15)
                    if response.status_code == 500:
                        error(f"{task_number} - Internal server error")
                        await asyncio.sleep(1)
                    elif response.status_code != 200:
                        error(f"{task_number} - Error getting token info: {response.status_code}")
                    else:
                        data = response.json()
                        if data['data'] == None:
                            if counter < 5:
                                counter += 1
                                error(f"{task_number} - No creator found for the token, retrying...")
                                await asyncio.sleep(5)
                            else:
                                break
                        if data and 'data' in data and 'owner' in data['data']:
                            coin["creator_wallet"] = data['data']['owner']
                            info(f"{task_number} - Creator Wallet: {coin['creator_wallet']}")
                            break
                        else:
                            error(f"{task_number} - Unexpected response format")
                            warn(data)
                            await asyncio.sleep(15)
            try:
                if coin['creator_wallet']:
                    await self.get_creator_tx(task_number,coin)
                else:
                    pass
            except:
                error(f"{task_number} - No data creator wallet found for token, skipping.")
                pass
        except Exception as e:
            error(f"{task_number} - Error getting creator wallet: {e}")

    async def get_creator_tx(self,task_number,coin):
        coin["creator_new_wallet"] = False
        coin["profit_owner"] = False
        creator_wallet = Pubkey.from_string(coin["creator_wallet"])
        try:
            info(f"{task_number} - Getting creator transactions")
            response = await self.solana_client.get_signatures_for_address(creator_wallet, limit=1000)
            if response.value:
                if len(response.value) > 400:
                    info(f"{task_number} - Wallet got enough transactions")
                    coin["creator_new_wallet"] = False
                else:
                    info(f"{task_number} - Wallet is new")
                    coin["creator_new_wallet"] = True
                if coin["creator_new_wallet"]:
                    coin["profit_owner"] = await self.check_creator_profit(task_number, coin)
                await self.check_owner_coins(task_number, coin)
        except Exception as e:
            error(f"{task_number} - Error getting creator transaction: {e}")

    async def check_creator_profit(self,task_number, coin):
        try:
            info(f"{task_number}- Checking profit for owner wallet")
            async with httpx.AsyncClient() as client:
                response = requests.get(
                    f"https://api.helius.xyz/v0/addresses/{str(coin['creator_wallet'])}/transactions?api-key={self.helius_apikey}",
                    headers={},
                )
                if response.status_code != 200:
                    error(f"{task_number} - Error checking profit in owner wallet: {response.status_code}")

                transactions = response.json()

                if not transactions:
                    info(f"{task_number} - No transactions found for owner wallet")

                token_trades = {}

                # Loop through each transaction
                for tx  in transactions:
                    if "SWAP" in tx["type"]:
                        token_transfers = tx.get("tokenTransfers", [])
                        native_transfers = tx.get("nativeTransfers", [])
                        for transfer in token_transfers:
                            mint = transfer["mint"]
                            token_amount = transfer["tokenAmount"] / (10 ** transfer.get("mintDecimals", 6))  
                            
                            
                            if transfer["toUserAccount"] == coin['creator_wallet']:  
                                sol_spent = sum(
                                    t["amount"] / 1e9 for t in native_transfers if t["fromUserAccount"] == coin['creator_wallet']
                                )  
                                if mint not in token_trades:
                                    token_trades[mint] = {"bought": [], "sold": []}
                                token_trades[mint]["bought"].append({"amount": token_amount, "cost": sol_spent})
                            
                            elif transfer["fromUserAccount"] == coin['creator_wallet']:  
                                sol_received = sum(
                                    t["amount"] / 1e9 for t in native_transfers if t["toUserAccount"] == coin['creator_wallet']
                                )  
                                if mint not in token_trades:
                                    token_trades[mint] = {"bought": [], "sold": []}
                                token_trades[mint]["sold"].append({"amount": token_amount, "revenue": sol_received})


                token_profits = {}
                total_profit = 0
                profitable_coins = 0
                total_coins = len(token_trades)
                for mint, trades in token_trades.items():
                    total_cost = sum(b["cost"] for b in trades["bought"])
                    total_revenue = sum(s["revenue"] for s in trades["sold"])
                    total_bought = sum(b["amount"] for b in trades["bought"])
                    total_sold = sum(s["amount"] for s in trades["sold"])
                    profit = total_revenue - total_cost
                    if profit > 0:
                        profitable_coins += 1
                    total_profit += profit
                    token_profits[mint] = {
                        "total_bought": total_bought,
                        "total_sold": total_sold,
                        "total_cost": total_cost,
                        "total_revenue": total_revenue,
                        "profit": profit,
                    }
                profit_percentage = (profitable_coins / total_coins * 100) if total_coins > 0 else 0
                if profit_percentage > 55:
                    info(f"{task_number}- Owner wallet is profitable")
                    return True
                else:
                    info(f"{task_number}- Owner wallet is not profitable")
                    return False
        except Exception as e:
            error(f"{task_number} - Error checking owner wallet profit: {e}")

    async def check_owner_coins(self,task_number, coin):
        coin["oldcoins"] = False
        try:
            info(f"{task_number} - Checking if dev created other coins.")
            async with httpx.AsyncClient() as client:
                response = await client.get(f"https://frontend-api-v2.pump.fun/balances/{coin['creator_wallet']}?limit=50&offset=0&minBalance=-1")
                data = response.json()
                if len(data) > 1:
                    coin["oldcoins"] = True
                    info(f"{task_number} - Dev created other coins: {(len(data))}")
                else:
                    coin["oldcoins"] = False
                    info(f"{task_number} - Dev never created any other coins")
                await self.get_holders(task_number, coin)
        except Exception as e:
            error(f"{task_number} - Error checking dev coins: {e}")

    async def get_holders(self,task_number,coin):
        try:
            info(f"{task_number} - Getting holders")
            total_supply = 0
            holders = []
            owner_supply = 0
            payload_getholders = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getProgramAccounts",
                "params": [
                    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    {
                        "encoding": "jsonParsed",
                        "filters": [
                            {"dataSize": 165},
                            {
                                "memcmp": {
                                    "offset": 0,
                                    "bytes": str(coin['token_address'])
                                }
                            }
                        ]
                    }
                ]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(self.rpc_url, json=payload_getholders, timeout=30)
                data = response.json()
                for account in data["result"]:
                    if self.addy_pf_bonding_curve not in account["account"]["data"]["parsed"]["info"]["owner"]:
                        amount = int(account["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"])
                        if amount > 0:
                            total_supply += amount
                            holders.append({
                                "owner": account["account"]["data"]["parsed"]["info"]["owner"],
                                "amount": amount
                            })
                        if str(coin['creator_wallet']) in account["account"]["data"]["parsed"]["info"]["owner"]:
                            owner_supply = int(account["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"])
                if total_supply > 0:
                    coin["owner_percentage"] = round((owner_supply/total_supply)*100,2)
                    coin["holder_number"] = len(holders)
                    holders = sorted(holders, key=lambda x: x["amount"], reverse=True)
                    top_10_supply = sum(holder["amount"] for holder in holders[:10])
                    coin["top10_wallets"] = {holder["owner"]: 0 for holder in holders[:10]}
                    coin["percentage_top_10"] = (top_10_supply / (total_supply - owner_supply)) * 100 if total_supply > 0 else 0

                    info(f"{task_number} - Owner Supply: {coin['owner_percentage']}")
                    info(f"{task_number} - Holders: {len(holders)}")
                    info(f"{task_number} - Top 10 Supply: {round(top_10_supply,1)}%")
                else:
                    coin["owner_percentage"] = 0
                    coin["percentage_top_10"] = 0
                    coin["holder_number"] = 0

            info(f"{task_number} - Top 10 Holder: {coin['percentage_top_10']}%")
            await self.run_all_tasks(task_number,coin, holders)
        except Exception as e:
            error(f"{task_number} - Error getting holders: {e}")

    async def run_all_tasks(self,task_number,coin,holders):
        coin["top_holders_good_traders"] = False
        try:
            categories = {
                ">900":0,
                "700-900": 0,
                "500-700": 0,
                "400-500": 0,
                "300-400": 0,
                "200-300": 0,
                "100-200": 0,
                "50-100": 0,
                "20-50": 0,
                "<20": 0
            }
            info(f"{task_number} - Running all holders wallets...")
            #tasks = [asyncio.create_task(self.process_holder(i)) for i in self.holders]
            max_concurrent_tasks = 30
            for i in range(0, len(holders), max_concurrent_tasks):
                batch = [holder["owner"] for holder in holders[i:i + max_concurrent_tasks]]
                tasks = [asyncio.create_task(self.process_holder(amount, task_number,categories,coin)) for amount in batch]
                await asyncio.gather(*tasks)
            percentages = {key: (value / len(holders)) * 100 for key, value in categories.items()}
            coin["new_wallets_percentage"] = percentages["<20"] + percentages["20-50"] + percentages["50-100"]
            info(f"{task_number} - New wallets percentage: {coin['new_wallets_percentage']}")
            coin["score"] = round((
                percentages[">900"] * 10 +
                percentages["700-900"] * 9 +
                percentages["500-700"] * 8 +
                percentages["400-500"] * 7 +
                percentages["300-400"] * 6 +
                percentages["200-300"] * 5 +
                percentages["100-200"] * 4 +
                percentages["50-100"] * 2 +
                percentages["20-50"] * 1 +
                percentages["<20"] * 0
            ) / 100,1)

            info(f"Score: {coin['score']}")
            profitable_wallets_count = 0
            tasks = []
            for wallet, count in coin["top10_wallets"].items():
                if count > 200:
                    info(f"{task_number}- Wallet: {wallet}, Count: {count}")
                    tasks.append(self.check_profit(wallet,task_number))
                else:
                    info(f"{task_number}- Wallet {wallet} has less than 200 transactions.")
            
            results = await asyncio.gather(*tasks)
            for wallet, result in zip(coin["top10_wallets"].keys(), results):
                if result:
                    info(f"{task_number}- Wallet {wallet} is profitable.")
                    profitable_wallets_count += 1
                else:
                    info(f"{task_number}- Wallet {wallet} is not profitable.")
            
            info(f"{task_number} - Profitable wallets count: {profitable_wallets_count}")
            if profitable_wallets_count > 5:
                info(f"{task_number} - Top holders are good traders")
                coin["top_holders_good_traders"] = True
            else:  
                info(f"{task_number} - Top holders are not good traders")
            coin["blacklist"] = await self.check_blacklist(task_number,coin)
            await self.process_data_and_send_to_b(task_number, coin)
            coin["status"] = await self.monitor_coin(task_number,coin)
            await self.add_coin_to_db(task_number,coin)
        except Exception as e:
            error(f"{task_number} - Error running all tasks: {e}")

    async def process_data_and_send_to_b(self, task_number,coin):
        info(f"{task_number} - Sending data to the AI model...")
        data = {
            "token_address":coin["token_address"],
            "token_name":coin["token_name"],
            "token_img":coin["token_img"],
            "blacklist":coin["blacklist"],
            "twitter_check":coin["twitter_check"],
            "telegram_check":coin["telegram_check"],
            "website_check":coin["website_check"],
            "creator_new_wallet":coin["creator_new_wallet"],
            "profit_owner":coin["profit_owner"],
            "oldcoins":coin["oldcoins"],
            "owner_percentage":coin["owner_percentage"],
            "holder_number":coin["holder_number"],
            "percentage_top_10":coin["percentage_top_10"],
            "score":coin["score"],
            "top_holders_good_traders":coin["top_holders_good_traders"],
            "new_wallets_percentage":coin["new_wallets_percentage"],
        }
        await self.class_b_instance.receive_data_from_a(data)

    async def process_holder(self, i,task_number,categories, coin):
        try:
            headers={"Content-Type":"application/json"}
            payload = {
                "jsonrpc":"2.0",
                "id":"1",
                "method":"getSignaturesForAddress",
                "params":[i]
            }
            async with httpx.AsyncClient() as client:
                while True:
                    try:
                        info(f"{task_number} - Processing holders: {i}")
                        response = await client.post(f"https://mainnet.helius-rpc.com/?api-key={self.helius_apikey}", json=payload, headers=headers, timeout=15)
                        data = response.json()
                        if "Too Many Requests" in str(response):
                            error(f"{task_number} - Rate limit while processing holder. Retrying...")
                            await asyncio.sleep(10)  
                        if response.status_code != 200:
                            error(f"{task_number} - Status error while processing holder: {response.status_code}")
                            warn(data)
                            await asyncio.sleep(10) 
                        if 'error' in data:
                            if data['error']['message'] == "Rate limit exceeded":
                                error(f"{task_number} - Rate limit while processing holder. Retrying...")
                                await asyncio.sleep(30)
                            else:
                                error(f"{task_number} - Error processing holder: {data['error']['message']}")
                                #print(data)
                                await asyncio.sleep(10)
                        try:
                            result =  data['result']
                            break
                        except Exception as e:
                            error(f"{task_number} - Error processing holders: {e}")
                            #warn(response.json())
                            await asyncio.sleep(10)
                    except Exception as e:
                        error(f"{task_number} - Error while processing holder {i} - {e}")
                        warn(response.json())
                        await asyncio.sleep(10)
                if i in coin["top10_wallets"]:
                    coin["top10_wallets"][i] = len(data['result'])
                if len(data['result']) > 900:
                    categories[">900"] += 1
                elif 700 < len(data['result']) < 900:
                    categories["700-900"] += 1
                elif 500 < len(data['result']) < 700:
                    categories["500-700"] += 1
                elif 400 < len(data['result']) < 500:
                    categories["400-500"] += 1
                elif 300 < len(data['result']) < 400:
                    categories["300-400"] += 1
                elif 200 < len(data['result']) < 300:
                    categories["200-300"] += 1
                elif 100 < len(data['result']) < 200:
                    categories["100-200"] += 1
                elif 50 < len(data['result']) < 100:
                    categories["50-100"] += 1
                elif 20 < len(data['result']) < 50:
                    categories["20-50"] += 1
                else:
                    categories["<20"] += 0
        except Exception as e:
            error(f"{task_number} - Error processing holder {i} - {e}")

    async def check_profit(self, i,task_number):
        try:
            info(f"{task_number}- Checking profit for wallet: {i}")
            async with httpx.AsyncClient() as client:
                while True:
                    response = requests.get(
                        f"https://api.helius.xyz/v0/addresses/{i}/transactions?api-key={self.helius_apikey}",
                        headers={},
                    )
                    if response.status_code == 500:
                        error(f"{task_number} - Error checking profit in wallet {i}: {response.status_code}")
                        warn(response.json())
                        await asyncio.sleep(10)
                    if response.status_code != 200:
                        error(f"{task_number} - Error checking profit in wallet {i}: {response.status_code}")
                        warn(response.json())
                        await asyncio.sleep(10)
                

                    transactions = response.json()

                    if not transactions:
                        info(f"{task_number} - No transactions found for wallet: {i}")

                    token_trades = {}

                    # Loop through each transaction
                    for tx  in transactions:
                        if "SWAP" in tx["type"]:
                            token_transfers = tx.get("tokenTransfers", [])
                            native_transfers = tx.get("nativeTransfers", [])
                            for transfer in token_transfers:
                                mint = transfer["mint"]
                                token_amount = transfer["tokenAmount"] / (10 ** transfer.get("mintDecimals", 6))  
                                
                                
                                if transfer["toUserAccount"] == i:  
                                    sol_spent = sum(
                                        t["amount"] / 1e9 for t in native_transfers if t["fromUserAccount"] == i
                                    )  
                                    if mint not in token_trades:
                                        token_trades[mint] = {"bought": [], "sold": []}
                                    token_trades[mint]["bought"].append({"amount": token_amount, "cost": sol_spent})
                                
                                elif transfer["fromUserAccount"] == i:  
                                    sol_received = sum(
                                        t["amount"] / 1e9 for t in native_transfers if t["toUserAccount"] == i
                                    )  
                                    if mint not in token_trades:
                                        token_trades[mint] = {"bought": [], "sold": []}
                                    token_trades[mint]["sold"].append({"amount": token_amount, "revenue": sol_received})

                    token_profits = {}
                    total_profit = 0
                    profitable_coins = 0
                    total_coins = len(token_trades)
                    for mint, trades in token_trades.items():
                        total_cost = sum(b["cost"] for b in trades["bought"])
                        total_revenue = sum(s["revenue"] for s in trades["sold"])
                        total_bought = sum(b["amount"] for b in trades["bought"])
                        total_sold = sum(s["amount"] for s in trades["sold"])
                        profit = total_revenue - total_cost
                        if profit > 0:
                            profitable_coins += 1
                        total_profit += profit
                        token_profits[mint] = {
                            "total_bought": total_bought,
                            "total_sold": total_sold,
                            "total_cost": total_cost,
                            "total_revenue": total_revenue,
                            "profit": profit,
                        }
                    break
                profit_percentage = (profitable_coins / total_coins * 100) if total_coins > 0 else 0
                if profit_percentage > 55:
                    return True
                else:
                    return False
        except Exception as e:
            error(f"{task_number} - Error checking profit: {e}")
        
    async def connect_to_db(self,task_number):
        try:
            conn = await asyncpg.connect(
                user='',
                password='',
                database='',
                host='',
                port=number
            )
            return conn
        except Exception as e:
            error(f"{task_number} - Errore durante la connessione al database: {e}")
            return None

    async def add_coin_to_db(self,task_number, coin):
        conn = await self.connect_to_db(task_number)
        info(f"{task_number} - Creating a random id")
        characters = string.ascii_letters + string.digits
        random_id = ''.join(random.choices(characters, k=12))
        if conn is None:
            return
        try:

            insert_query = """
            INSERT INTO coins (
                id,token_address,token_name,token_img ,blacklist ,twitter_check ,telegram_check ,website_check ,creator_new_wallet ,profit_owner ,oldcoins ,owner_percentage ,holder_number ,percentage_top_10 ,score ,top_holders_good_traders ,new_wallets_percentage ,success
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18
            );
            """
            
            await conn.execute(insert_query,
                random_id,str(coin["token_address"]),coin["token_name"],coin["token_img"],coin["blacklist"],coin["twitter_check"],coin["telegram_check"],coin["website_check"],coin["creator_new_wallet"],coin["profit_owner"],coin["oldcoins"],int(coin["owner_percentage"]),int(coin["holder_number"]),int(coin["percentage_top_10"]),int(coin["score"]),coin["top_holders_good_traders"],coin["new_wallets_percentage"],coin["status"]
            )
            info(f"{task_number} - Dati inseriti con successo nel database.")
        except Exception:
            error(f"Errore durante l'inserimento dei dati")
        finally:
            await conn.close()

    async def monitor_coin(self, task_number,coin):
        check_scam = False
        check_range = False
        url = "https://public-api.birdeye.so/defi/v3/token/market-data?address={}".format(str(coin["token_address"]))
        headers = {
            "accept": "application/json",
            "x-chain": "solana",
            "X-API-KEY": self.birdeye_apikey
        }
        while True:
            try:
                info(f"{task_number} - Monitoring coin...")
                async with httpx.AsyncClient() as client:
                    response = await client.get(url=url, headers=headers, timeout=15)
                    if response.status_code == 500:
                        error(f"{task_number} - Internal server error while monitoring coin. Retrying...")
                        await asyncio.sleep(20)
                    if response.status_code == 429:
                        error(f"{task_number} - Rate limit error while monitoring coin. Retrying...")
                        await asyncio.sleep(20)
                    if response.status_code != 200:
                        error(f"{task_number} - Error monitoring coin: {response.status_code}")
                        await asyncio.sleep(20)
                    else:
                        data = response.json()
                        if check_scam:
                            try:
                                if data["data"]["marketcap"] > 150000:
                                    info(f"{task_number} - Price change detected: {data['data']['marketcap']}")
                                    return True
                                elif data["data"]["marketcap"] < 25000:
                                    info(f"{task_number} - Price change detected: {data['data']['marketcap']}")
                                    return False
                            except KeyError:
                                if data["data"]["price"] > 0.0005:
                                    info(f"{task_number} - Price change detected, using price: {data['data']['price']}")
                                    return True
                                elif data["data"]["price"] < 0.000025:
                                    info(f"{task_number} - Price change detected, using price: {data['data']['price']}")
                                    return False
                            finally:
                                if not check_range:
                                    info(f"{task_number} - Coin is in range to check scam, monitoring...")
                                    await asyncio.sleep(20)
                        else:
                            try:
                                if data["data"]["marketcap"] > 500000:
                                    info(f"{task_number} - Price change detected, wainting 10 minutes to check scam")
                                    check_scam = True
                                    await asyncio.sleep(600)
                                elif data["data"]["marketcap"] < 25000:
                                    info(f"{task_number} - Price change detected: {data['data']['marketcap']}")
                                    return False
                            except KeyError:
                                if data["data"]["price"] > 0.0005:
                                    info(f"{task_number} - Price change detected, wainting 10 minutes to check scam")
                                    check_scam = True
                                    await asyncio.sleep(600)
                                elif data["data"]["price"] < 0.000025:
                                    info(f"{task_number} - Price change detected, using price: {data['data']['price']}")
                                    return False
                            finally:
                                if not check_range:
                                    info(f"{task_number} - Coin is in range, monitoring...")
                                    await asyncio.sleep(20)
            except Exception as e:
                error(f"{task_number} - Error monitoring coin: {e}")
                warn(data)
                await asyncio.sleep(20)

    async def check_blacklist(self,task_number,coin):
        info(f"{task_number} - Checking blacklist...")
        try:
            with open("symbol.json", 'r') as file:
                data = json.load(file)
        except FileNotFoundError:
            data = {}
        except json.JSONDecodeError:
            data = {}

        if coin['token_name'] not in data:
            data.append(coin['token_name']) 
            with open("symbol.json", 'w') as file:
                json.dump(data, file, indent=4)
            
            info(f"{task_number} - Added '{coin['token_name']}' to the blacklist.")
            return False
        else:
            info(f"'{task_number} - {coin['token_name']}' is already used, blacklisted!")
            return True

class AI:
    def __init__(self):
        self.model = XGBClassifier(
            eval_metric="logloss",  
            scale_pos_weight=1,     
            n_estimators=100,       
            learning_rate=0.1,      
            max_depth=6,            
            random_state=42         
        )
        self.connection = None
        self.is_fitted = False
        self.label_encoders = {}  
        self.best_model = None

    async def start(self, class_a_instance):
        warn("AI: Starting process...")
        self.class_a_instance = class_a_instance
        await self.train_model_with_tuning()

    async def connect_to_db(self):
        """Connect to the PostgreSQL database."""
        if not self.connection:
            self.connection = await asyncpg.connect(
                user='',
                password='',
                database='',
                host='',
                port=number
            )
        return self.connection

    async def fetch_data(self):
        """Fetch data from the database."""
        warn("AI: Fetching data from the database...")
        conn = await self.connect_to_db()
        query = "SELECT * FROM coins;"
        rows = await conn.fetch(query)
        data = [dict(row) for row in rows] 
        return pd.DataFrame(data)

    async def preprocess_data(self, data):
        """Prepare infos for training."""
        categorical_columns = [
            "blacklist", "twitter_check", "website_check",
            "creator_new_wallet", "profit_owner", "oldcoins", "top_holders_good_traders", "success"
        ]

        for col in categorical_columns:
            if col in data.columns:
                if col not in self.label_encoders:
                    self.label_encoders[col] = LabelEncoder()
                    data[col] = self.label_encoders[col].fit_transform(data[col].astype(str))
                else:
                    data[col] = self.label_encoders[col].transform(data[col].astype(str))

        X = data.drop(columns=["id", "token_address", "token_name", "token_img", "success"])
        y = data["success"]

        return X, y

    async def train_model_with_tuning(self):
        warn("AI: Training and tuning the model...")

        data = await self.fetch_data()
        X, y = await self.preprocess_data(data)
        print(X)
        print(y)
        scale_pos_weight = len(y[y == 0]) / len(y[y == 1])

        model = XGBClassifier(
            objective="binary:logistic",
            eval_metric="auc",
            scale_pos_weight=scale_pos_weight,
            n_jobs=-1
        )

        param_grid = {
            "max_depth": [3, 5, 7],
            "learning_rate": [0.01, 0.1, 0.2],
            "n_estimators": [50, 100, 200],
            "subsample": [0.8, 1.0],
            "colsample_bytree": [0.8, 1.0],
        }

        kfold = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

        grid_search = GridSearchCV(
            estimator=model,
            param_grid=param_grid,
            scoring=make_scorer(roc_auc_score, needs_proba=True),
            cv=kfold,
            verbose=2,
            n_jobs=-1
        )

        grid_search.fit(X, y)

        self.best_model = grid_search.best_estimator_
        warn(f"Best Parameters: {grid_search.best_params_}")

        y_pred = self.best_model.predict(X)
        y_proba = self.best_model.predict_proba(X)[:, 1]
        info("AI: \nClassification Report:")
        info(classification_report(y, y_pred))
        info(f"AI: AUC-ROC Score: {roc_auc_score(y, y_proba):.4f}")

    async def receive_data_from_a(self, data):
        info("AI: Received data from Bot A.")
        data = data
        prediction = await self.predict_new_coin(data)
        info(f"AI: Success probability for new coin: {prediction}")
        data = {"prediction": prediction}
        info("AI: Sending data to Bot A.")

    async def predict_new_coin(self, data):
        """Predict the success probability of a new coin."""
        try:
            new_data = {
                "blacklist":data["blacklist"],
                "twitter_check":data["twitter_check"],
                "telegram_check":data["telegram_check"],
                "website_check":data["website_check"],
                "creator_new_wallet":data["creator_new_wallet"],
                "profit_owner":data["profit_owner"],
                "oldcoins":data["oldcoins"],
                "owner_percentage":data["owner_percentage"],
                "holder_number":data["holder_number"],
                "percentage_top_10":data["percentage_top_10"],
                "score":data["score"],
                "top_holders_good_traders":data["top_holders_good_traders"],
                "new_wallets_percentage":data["new_wallets_percentage"],
            }
            if not self.best_model:
                raise ValueError("The model is not trained yet.")

            new_coin_df = pd.DataFrame([new_data])
            categorical_columns = [
                "blacklist", "twitter_check", "website_check",
                "creator_new_wallet", "profit_owner", "oldcoins", "top_holders_good_traders"
            ]

            for col in categorical_columns:
                if col in new_coin_df.columns:
                    if col not in self.label_encoders:
                        self.label_encoders[col] = LabelEncoder()
                        new_coin_df[col] = self.label_encoders[col].fit_transform(new_coin_df[col].astype(str))
                    else:
                        new_coin_df[col] = self.label_encoders[col].transform(new_coin_df[col].astype(str))

            success_probability = self.best_model.predict_proba(new_coin_df)[:, 1][0]
            print(success_probability)
            info(f"Prediction completed: {success_probability * 100:.2f}%")
            if success_probability > 0.5:
                await self.send_to_discord(data, success_probability)
            else: 
                pass
            return success_probability

        except Exception as e:
            error(f"Error during prediction: {e}")
            raise

    async def send_to_discord(self, data, success_probability):
        """
        Sends the prediction result to a Discord webhook.
        
        You will need to add some more stuff its very basic now
        """
        try:
            async with httpx.AsyncClient() as client:
                message = {
                    "content": None,
                    "embeds": [
                        {
                            "title": "AI Prediction Result",
                            "description": "Details about the new coin.",
                            "fields": [
                                {"name": "Token Name", "value": str(data["token_name"]), "inline": True},
                                {"name": "Contract Address", "value": str(data["token_address"]), "inline": True},
                                {"name": "Success Probability", "value": f"{success_probability * 100:.2f}%", "inline": True},
                                {"name": "Dex Screener", "value": f"https://dexscreener.com/solana/{str(data['token_address'])}", "inline": True}
                            ],
                            "color": 3066993,  # Green color
                            "image": {"url": str(data["token_img"])}
                        }
                    ]
                }
                response = await client.post("https://discord.com/api/webhooks/1332508364961484800/KmvWf7GKZD0giNO8R2q3wQaAKJ8F0TDrzKGa57pxzcuFtgK0mR26vLdaGCuUQO-Bnt-j", json=message)
                if response.status_code == 204:
                    info("Prediction result sent to Discord successfully.")
                else:
                    error(f"Failed to send prediction result to Discord. Status Code: {response.status_code}")
        except Exception as e:
            error(f"Error sending data to Discord: {e}")


async def main():
    class_a = BotMain()
    class_b = AI()
    await asyncio.gather(
        class_b.start(class_a),
        class_a.run(class_b)
    )

asyncio.run(main())