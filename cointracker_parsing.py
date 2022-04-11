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

def round_float(num):
    return round(num, 11)

def parse_date(date_string):
    try:
        return datetime.strptime(date_string, '%m/%d/%Y %H:%M:%S')
    except:
        return datetime.strptime(date_string, '%m/%d/%Y')

def date_to_string(datetime_date):
    # print(datetime_date)
    # print(hasattr(datetime_date, 'second'))
    # print(getattr(datetime_date, 'second'))
    
    # if datetime_date.second == 0 and datetime_date.minute == 0 and datetime_date.hour == 0:
    if not hasattr(datetime_date, 'second'):
        return datetime.strftime(datetime_date, '%m/%d/%Y')
    else:
        return datetime.strftime(datetime_date, '%m/%d/%Y %H:%M:%S')


def sort_buy_history(bought_dict, coin=None, sort='HIFO'):
    for coin_name, history in bought_dict.items():
        if coin == coin_name or coin is None:
            if sort == 'FIFO':
                new_history = sorted(history, reverse=False, key=lambda i: i[0])
            elif sort == 'LIFO':
                new_history = sorted(history, reverse=True, key=lambda i: i[0])
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
            net = recieved_money - cost_basis
            num_coins = to_sell_amount

            if abs(net) > 0.01:
                row_entry = [date_to_string(sell_date), sold_coin, round_float(num_coins), date_to_string(buy_date), round_float(cost_basis),  round_float(recieved_money), net]
                out_lines.append(row_entry)

            new_tup = (buy_date, current_amount-to_sell_amount, price_per_coin)
            coin_history[idx] = new_tup
            to_sell_amount = 0
            break

        elif to_sell_amount >= current_amount:
            cost_basis = price_per_coin * current_amount
            recieved_money = sold_price_per_coin * current_amount
            net = recieved_money - cost_basis
            num_coins = current_amount

            if abs(net) > 0.01:
                row_entry = [date_to_string(sell_date), sold_coin, round_float(num_coins), date_to_string(buy_date), round_float(cost_basis), round_float(recieved_money), net]
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
    assets_file = "assets.csv"
    full_path = os.path.join(dir_path, file)
    out_path = os.path.join(dir_path, out_file)
    assets_path = os.path.join(dir_path, assets_file)

    out_collapsed_file = "out_collapsed.csv"
    out_collapsed_path = os.path.join(dir_path, out_collapsed_file)

    sell_scheme = 'HIFO'
    force_ltcg = False

    new_header = ['Date Sold', 'Name', 'Coin Amount', 'Purchase Date', 'Cost Basis',  'Proceeds', 'Net', 'ForceLTCG_%s' % force_ltcg, 'Scheme_%s' % sell_scheme]
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
                elif force_ltcg and (buy_date >= sell_date - relativedelta(years=1, days=1)):
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

    # for line in out_lines:
    #     print(line)
    # Check last line
    # if last line shares buy Date, sell Date, buy price per coin, sell price per coin. last line and current line
    # 
    # when current line is different from last line, add current line to new_lines

    # when no more lines, add current line to new_lines
    def check_line_match(line1, line2):
        coin_type1 = line1[1]
        coin_type2 = line2[1]
        if coin_type1 != coin_type2:
            print('diff coins')
            return False

        sell_date1 = parse_date(line1[0])
        sell_date2 = parse_date(line2[0])
        if sell_date1.date() != sell_date2.date():
            print('diff sell_date1')
            return False

        buy_date1 = parse_date(line1[3])
        buy_date2 = parse_date(line2[3])
        if buy_date1.date() != buy_date2.date():
            print('diff buy_date1')
            return False

        num_coin1 = line1[2]
        num_coin2 = line2[2]

        ppc_buy_1 = line1[4] / num_coin1
        ppc_buy_2 = line2[4] / num_coin2
        if not (ppc_buy_1 > (ppc_buy_2*.99) and ppc_buy_1 < (ppc_buy_2*1.01)):
            print('diff ppc_buy_1')
            print(round(ppc_buy_1, 1), round(ppc_buy_2, 1))
            print(ppc_buy_1 > (ppc_buy_2*.99), ppc_buy_1, (ppc_buy_2*.99))
           # print(ppc_buy_1 > (ppc_buy_2*.99), ppc_buy_1, (ppc_buy_2*.99))
            return False

        ppc_sell_1 = line1[5] / num_coin1
        ppc_sell_2 = line2[5] / num_coin2
        if not (ppc_sell_1 > (ppc_sell_2*.999) and ppc_sell_1 < (ppc_sell_2*1.001)):
            print('diff ppc_sell_1')
            print(round(ppc_sell_1, 1), round(ppc_sell_2, 1))
            return False

        return True

    
    def merge_lines(line1, line2):
        new_line = line1
        new_line[0] = date_to_string(parse_date(line1[0]).date())
        new_line[2] = line1[2] + line2[2]
        new_line[3] = date_to_string(parse_date(line1[3]).date())
        new_line[4] = line1[4] + line2[4]
        new_line[5] = line1[5] + line2[5]
        new_line[6] = line1[6] + line2[6]

        return new_line

    def collapse_lines(original_lines):
        new_lines = []
        previous_line = None
        for line in original_lines:
            current_line = line
            if previous_line is None:
                pass
            else:
                if check_line_match(previous_line, current_line):
                    current_line = merge_lines(previous_line, current_line)
                else:
                    new_lines.append(previous_line)
            previous_line = current_line
        new_lines.append(previous_line)
        return new_lines


# row_entry = [date_to_string(sell_date), sold_coin, round_float(num_coins), date_to_string(buy_date), round_float(cost_basis), round_float(recieved_money), net]


    with open(out_path, 'w') as f:
        for line in out_lines:
            str_out = ''
            for x in line:
                str_out += '%s,' % x
            
            str_out = str_out[:-1]
            str_out += '\n'
            f.write(str_out)


    collapsed_lines = collapse_lines(out_lines)
    with open(out_collapsed_path, 'w') as f:
        for line in collapsed_lines:
            str_out = ''
            for x in line:
                str_out += '%s,' % x
            
            str_out = str_out[:-1]
            str_out += '\n'
            f.write(str_out)


    asset_lines = [['Name', 'Purchase Date', 'Current Held', 'Price Per Coin']]
    for coin_type in bought_dict:
        for buy_transaction in bought_dict[coin_type]:
            buy_date = buy_transaction[0]
            current_amount = buy_transaction[1]
            price_per_coin = buy_transaction[2]
            row_entry = [coin_type, buy_date, round_float(current_amount), round_float(price_per_coin)]
            asset_lines.append(row_entry)

    with open(assets_path, 'w') as f:
        for line in asset_lines:
            str_out = ''
            for x in line:
                str_out += '%s,' % x
            
            str_out = str_out[:-1]
            str_out += '\n'
            f.write(str_out)

if __name__ == "__main__":
    main()
