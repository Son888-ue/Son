import asyncio
import websockets
import json
import os

API_TOKEN = os.getenv("DERIV_API_TOKEN")
SYMBOL = "1HZ10V"
DURATION = 2
AMOUNT = 5
PROFIT_THRESHOLD = 0.1

async def run_bot():
    async with websockets.connect("wss://ws.derivws.com/websockets/v3?app_id=1089") as ws:
        async def send(data):
            await ws.send(json.dumps(data))

        async def recv():
            return json.loads(await ws.recv())

        # Authorize
        await send({"authorize": API_TOKEN})
        auth_response = await recv()
        if 'error' in auth_response:
            print("Authorization Error:", auth_response['error']['message'])
            return

        print("Authorized")

        def candle_req():
            return {
                "ticks_history": SYMBOL,
                "adjust_start_time": 1,
                "count": 2,
                "end": "latest",
                "style": "candles",
                "granularity": 300,
                "subscribe": 0
            }

        await send(candle_req())
        candles = await recv()

        try:
            c1 = candles["candles"][0]["open"]
            c2 = candles["candles"][1]["open"]
        except Exception as e:
            print("Candle data error:", e)
            return

        if c1 != c2:
            print(f"Opening trade... Open1: {c1}, Open2: {c2}")
            await send({
                "buy": 1,
                "price": AMOUNT,
                "parameters": {
                    "amount": AMOUNT,
                    "basis": "stake",
                    "contract_type": "CALL",
                    "currency": "USD",
                    "duration": DURATION,
                    "duration_unit": "m",
                    "symbol": SYMBOL
                }
            })
            buy_response = await recv()
            if 'error' in buy_response:
                print("Buy error:", buy_response['error']['message'])
                return

            contract_id = buy_response['buy']['contract_id']
            print("Trade started. Contract ID:", contract_id)

            # Subscribe to proposal open contract
            await send({
                "proposal_open_contract": 1,
                "contract_id": contract_id
            })

            while True:
                poc_update = await recv()
                if "proposal_open_contract" in poc_update:
                    poc = poc_update["proposal_open_contract"]
                    if poc["is_valid_to_sell"] and poc.get("bid_price", 0) >= PROFIT_THRESHOLD:
                        print(f"Sell triggered at price: {poc['bid_price']}")
                        await send({
                            "sell": contract_id,
                            "price": poc["bid_price"]
                        })
                        sell_response = await recv()
                        print("Sell response:", sell_response)
                        break
                elif "error" in poc_update:
                    print("Error in contract:", poc_update['error']['message'])
                    break
        else:
            print("Condition not met: Candle1 == Candle2")

if __name__ == "__main__":
    asyncio.run(run_bot())
