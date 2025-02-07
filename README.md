# Shitcoins-AI
Shitcoins-AI is an AI-powered tool designed to predict whether a newly launched cryptocurrency can succeed. It analyzes coins after the bonding curve phase of pump.fun to assess their potential.

## 🔍How It Works
The bot is triggered whenever a new coin exits **Pump.fun** and begins bonding to list on **Raydium**. Once detected, it collects and analyzes multiple factors, such as:

- **Holders distribution**
- **Creator wallet activity**
- **Holders activity**
- **Check if the top 10 holders are profitable traders**
- **Gives a score to all the wallets based on how many tx they got**
Based on this data, the AI assigns a **success probability** by comparing the new coin’s characteristics to historical data stored in the database.

**Note:** Before fully running the AI, you must first **populate the database** with past coin data.

## ⚙️ How to Run
### 1️⃣ Setup Configuration
Edit the `config.json` file and provide the following credentials:
- `rpc_url`
- `Discord webhook`
- `Helius Dev API key` - https://dashboard.helius.dev/login?redirectTo=dashboard
- `Birdeye API key` - https://bds.birdeye.so/user/overview

### 2️⃣ Create the Database
1. Set up a **PostgreSQL database**, either locally or on a server. - https://www.youtube.com/watch?v=KuQUNHCeKCk

2. Create a table named `coins` with the following columns:
```
id, token_address, token_name, token_img, blacklist, 
twitter_check, telegram_check, website_check, creator_new_wallet, 
profit_owner, oldcoins, owner_percentage, holder_number, 
percentage_top_10, score, top_holders_good_traders, 
new_wallets_percentage, success
```

3. Open `main.py` and find the function `async def connect_to_db` (there are two instances of this function).
- Insert your **PostgreSQL credentials** to establish a database connection.

### 3️⃣ Populate the Database
Before running the AI, you need to populate the database with real coin data.

1. Open `main.py` and locate **line 485**, then comment out the following line:

```
# await self.process_data_and_send_to_b(task_number, coin)
```

2. Similarly, on **line 809**, comment out this line:

```
# await self.train_model_with_tuning()
```
3. Now, start the program by running:
```
py main.py
```
4. The bot will begin collecting real data and storing it in the database.
5. Wait until you have at least **5,000 coins** stored in the database.

### 4️⃣ Run the AI
Once the database is populated, it's time to enable the AI!

1. Open main.py and remove the # comments on lines 485 and 809 to reactivate AI processing:

```
await self.process_data_and_send_to_b(task_number, coin)
await self.train_model_with_tuning()
```
2. Run the bot again:
```
py main.py
```
3. The AI will now process incoming data and provide predictions based on historical trends.
#### You're all set! 🚀

## ⚠️ Disclaimer
- If you encounter issues with the **holder processing function**, it’s likely due to API rate limits.
  - To mitigate this, adjust the transaction check rate in **line 439** (default is 30).
- No major bugs were found during testing, but if you run into any problems, feel free to **contact me** for help.

## 💡 Final Thoughts
This was my first experience developing an AI, and I had a lot of fun working on it!
I hope it proves useful to someone. 🚀
