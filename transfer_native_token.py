import asyncio
from web3 import AsyncWeb3, AsyncHTTPProvider
from web3.exceptions import TransactionNotFound


rpc_url = 'https://rpc.ankr.com/arbitrum'
explorer_url = 'https://arbiscan.io/'

wallet_private_key = input("Введите приватный ключ отправителя: ").strip()

w3_client = AsyncWeb3(AsyncHTTPProvider(rpc_url))

sender_address = w3_client.to_checksum_address(w3_client.eth.account.from_key(wallet_private_key).address)
print(f"Ваш адрес: {sender_address}")

receiver_address = input("Введите адрес получателя: ").strip()
amount_eth = float(input("Введите сумму для отправки (в ETH): "))

async def get_balance(address):
    balance = await w3_client.eth.get_balance(address)
    return w3_client.from_wei(balance, 'ether')

async def get_priotiry_fee() -> int:
    fee_history = await w3_client.eth.fee_history(5, 'latest', [80.0])
    non_empty_block_priority_fees = [fee[0] for fee in fee_history["reward"] if fee[0] != 0]

    divisor_priority = max(len(non_empty_block_priority_fees), 1)
    priority_fee = int(round(sum(non_empty_block_priority_fees) / divisor_priority))

    return priority_fee


async def sign_and_send_tx(transaction):
    signed_raw_tx = w3_client.eth.account.sign_transaction(transaction, wallet_private_key).raw_transaction

    print('Успешно подписана транзакция!')

    tx_hash_bytes = await w3_client.eth.send_raw_transaction(signed_raw_tx)

    print('Успешно отправлена транзакция!')

    tx_hash_hex = w3_client.to_hex(tx_hash_bytes)

    return tx_hash_hex


async def wait_tx(tx_hash):
    total_time = 0
    timeout = 120
    poll_latency = 10
    while True:
        try:
            receipts = await w3_client.eth.get_transaction_receipt(tx_hash)
            status = receipts.get("status")
            if status == 1:
                print(f'Transaction was successful: {explorer_url}tx/{tx_hash}')
                return True
            elif status is None:
                await asyncio.sleep(poll_latency)
            else:
                print(f'Transaction failed: {explorer_url}tx/{tx_hash}')
                return False
        except TransactionNotFound:
            if total_time > timeout:
                print(f"Transaction is not in the chain after {timeout} seconds")
                return False
            total_time += poll_latency
            await asyncio.sleep(poll_latency)


async def main():

    sender_balance = await get_balance(sender_address)
    receiver_balance = await get_balance(receiver_address)

    print(f'Баланс отправителя до транзакции: {sender_balance} ETH')
    print(f'Баланс получателя до транзакции: {receiver_balance} ETH')

    if sender_balance < amount_eth:
        print("Ошибка: недостаточно средств для выполнения транзакции.")
        return

    transaction = {
        'chainId': await w3_client.eth.chain_id,
        'nonce': await w3_client.eth.get_transaction_count(sender_address),
        'from': sender_address,
        'to': w3_client.to_checksum_address(receiver_address),
        'value': w3_client.to_wei(amount_eth, 'ether'),
        'gasPrice': int((await w3_client.eth.gas_price) * 1.25)
    }

    if eip_1559:
        del transaction['gasPrice']

        base_fee = await w3_client.eth.gas_price
        max_priority_fee_per_gas = await w3_client.eth.max_priority_fee

        if max_priority_fee_per_gas == 0:
            max_priority_fee_per_gas = base_fee

        max_fee_per_gas = int(base_fee * 1.25 + max_priority_fee_per_gas)

        transaction['maxPriorityFeePerGas'] = max_priority_fee_per_gas
        transaction['maxFeePerGas'] = max_fee_per_gas
        transaction['type'] = '0x2'

    transaction['gas'] = int((await w3_client.eth.estimate_gas(transaction)) * 1.5)

    tx_hash = await sign_and_send_tx(transaction)
    await wait_tx(tx_hash)

    updated_sender_balance = await get_balance(sender_address)
    updated_receiver_balance = await get_balance(receiver_address)

    print(f"Баланс отправителя после транзакции: {updated_sender_balance} ETH")
    print(f"Баланс получателя после транзакции: {updated_receiver_balance} ETH")

eip_1559 = True
asyncio.run(main())

