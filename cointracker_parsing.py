import csv
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta


def read_csv(full_path):
    buy_lines = []
    sell_lines = []
    with open(full_path, 'r') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        for row in reader:
            if len(row) < 3:
                continue
            if row[1] == 'Buy':
                buy_lines.append(row)
            elif row[1] == 'Sell':
                sell_lines.append(row)
    return buy_lines, sell_lines


def parse_buy_lines(buy_lines):
    bought_dict = dict()
    for line in buy_lines:            
        coin = line[4]
        if line[1] == 'Buy':
            if coin != 'USD' and coin != '':
                if coin not in bought_dict:
                    bought_dict[coin] = []
                date = parse_date(line[0])
                amount = float(line[3])
                price_per_coin = float(line[11])/amount
                bought_dict[coin].append((date, amount, price_per_coin))
    return bought_dict


def parse_date(date_string):
    return datetime.strptime(date_string, '%m/%d/%Y %H:%M:%S')


def date_to_string(datetime_date):
    return datetime.strftime(datetime_date, '%m/%d/%Y %H:%M:%S')


def sort_buy_history(bought_dict, coin=None, sort='HIFO'):
    for coin_name, history in bought_dict.items():
        if coin == coin_name or coin is None:
            if sort == 'FIFO':
                new_history = sorted(history, reverse=True)
            elif sort == 'LIFO':
                new_history = sorted(history, reverse=False)
            elif sort == 'HIFO':
                new_history = sorted(history, reverse=True, key=lambda i: i[2])
            else:
                raise ValueError("Unrecognized sort type: %s.  Must be FIFO, LIFO, or HIFO" % sort)
            bought_dict[coin_name] = new_history
    return bought_dict


def sell_off_coins(coin_history, sell_date, to_sell_amount, sold_coin, sold_price_per_coin):
    out_lines = []
    for idx, tup in enumerate(coin_history):
        buy_date = tup[0]
        current_amount = tup[1]
        price_per_coin = tup[2]

        if current_amount == 0:
            continue

        elif current_amount > to_sell_amount:
            cost_basis = price_per_coin * to_sell_amount
            recieved_money = sold_price_per_coin * to_sell_amount
            proceeds = recieved_money - cost_basis
            num_coins = to_sell_amount

            row_entry = [date_to_string(sell_date), sold_coin, num_coins, date_to_string(buy_date), cost_basis,  recieved_money, proceeds]
            out_lines.append(row_entry)

            new_tup = (buy_date, current_amount-to_sell_amount, price_per_coin)
            coin_history[idx] = new_tup
            to_sell_amount = 0
            break

        elif to_sell_amount >= current_amount:
            cost_basis = price_per_coin * current_amount
            recieved_money = sold_price_per_coin * current_amount
            proceeds = recieved_money - cost_basis
            num_coins = current_amount

            row_entry = [date_to_string(sell_date), sold_coin, num_coins, date_to_string(buy_date), cost_basis, recieved_money, proceeds]
            out_lines.append(row_entry)

            new_tup = (buy_date, 0, price_per_coin)
            coin_history[idx] = new_tup

            to_sell_amount = to_sell_amount - current_amount
            continue
    return coin_history, to_sell_amount, out_lines


def main():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    file = "transactions_HIFO_Universal.csv"
    out_file = "out.csv"
    full_path = os.path.join(dir_path, file)
    out_path = os.path.join(dir_path, out_file)

    sell_scheme = 'HIFO'

    new_header = ['Date Sold', 'Name', 'Coin Amount', 'Purchase Date', 'Cost Basis',  'Sell Price', 'Proceeds']
    out_lines = []
    out_lines.append(new_header)

    buy_lines, sell_lines = read_csv(full_path)

    bought_dict = parse_buy_lines(buy_lines)        
    bought_dict = sort_buy_history(bought_dict, sort=sell_scheme)
    
    for line in sell_lines:
        if line[4] == 'USD' and line[4] != '':
            sell_date = parse_date(line[0])
            sold_coin = line[12]
            sold_amount = float(line[11])
            usd_recieved = float(line[3])
            sold_price_per_coin = usd_recieved / sold_amount

            coin_history = bought_dict[sold_coin]

            future_list = []
            stcg_list = []
            ltcg_list = []            

            for tup in coin_history:
                buy_date = tup[0]

                if buy_date >= sell_date:
                    future_list.append(tup)
                elif buy_date >= sell_date - relativedelta(years=1, days=1):
                    stcg_list.append(tup)
                else:
                    ltcg_list.append(tup)
            
            ltcg_list, leftover_to_sell, new_lines = sell_off_coins(ltcg_list, sell_date, sold_amount, sold_coin, sold_price_per_coin)
            out_lines += new_lines

            if leftover_to_sell != 0:
                print('Moving into short term capital gains')
                stcg_list, leftover_to_sell, new_lines = sell_off_coins(stcg_list, sell_date, leftover_to_sell, sold_coin, sold_price_per_coin)
                out_lines += new_lines
                
            if leftover_to_sell != 0:
                raise ValueError("Trying to sell more coin than we ever bought.")

            bought_dict[sold_coin] = future_list + stcg_list + ltcg_list
            bought_dict = sort_buy_history(bought_dict, coin=sold_coin, sort=sell_scheme)

    for line in out_lines:
        print(line)
    
    with open(out_path, 'w') as f:
        for line in out_lines:
            for x in line:
                f.write('%s,' % x)
            f.write('\n')

if __name__ == "__main__":
    main()
