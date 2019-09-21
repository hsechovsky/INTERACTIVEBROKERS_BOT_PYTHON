import pandas as pd
from user_data import *
from plan import daily_risk
from handle_data import handler
import time
from indicat import indicators
from strategy import strategy
import pytz
import datetime as dt
import pickle
from chart import chart
from calendario import cal_list


import logging
logging.basicConfig( filename= (f"./execution.log"),
                     filemode='w',
                     level=logging.ERROR,
                     format= '%(asctime)s - %(levelname)s - %(message)s',
                     datefmt= "%Y-%m-%d %H:%M:%S"
                   )


class trading_execution():

    def __init__ (self, plan, orders, trades):
        self.orders = orders
        self.trades = trades
        self.plan = plan

        self.handle = handler()
        self.strat = strategy(self.plan)
        self.ind = indicators()



    def current_time(self):
        x = dt.datetime.now(tz=pytz.timezone('Europe/Moscow')).hour * 100 + dt.datetime.utcnow().minute

        return x



    def time_to_minutes(self, time_std):
        hour_to_minute = time_std.hour * 60
        
        return hour_to_minute + time_std.minute



    def change_start(self, i): 
        waiting = min([self.plan.get(i)['strat'].get(ii) for ii in self.plan.get(i)['strat'].keys()])

        self.plan.get(i).update({
            'start': int(
                str(pd.to_datetime((self.time_to_minutes(dt.datetime.now(tz=pytz.timezone('Europe/Moscow')).time()) + waiting), unit='m').time().hour) + 
                str(pd.to_datetime((self.time_to_minutes(dt.datetime.now(tz=pytz.timezone('Europe/Moscow')).time()) + waiting), unit='m').time().minute) 
                )
            })



    def check_duration(self, i): 
        order_time = self.time_to_minutes(self.orders.get(i)['entry_time']) 
        duration = self.time_to_minutes(self.plan.get(i)['duration']) 

        if (order_time + duration) < self.time_to_minutes(dt.datetime.now(tz=pytz.timezone('Europe/Moscow')).time()): 
            return True
        else:
            return False



    def add_log(self, i, trade_id):

        try:
            target_stop = [self.orders.get(i)['targetID'], self.orders.get(i)['stopID']]
            last_trade = self.handle.last_trade(trade_id)

            if self.orders.get(i)['asset'] == last_trade[2] and last_trade[0] in target_stop:
                self.change_start(i)

                close_price = last_trade[1]


                self.trades.update({self.orders.get(i)['tradeID']:{

                    'asset': self.orders.get(i)['asset'],
                    'entry_date': self.orders.get(i)['entry_date'],
                    'entry_time': self.orders.get(i)['entry_time'],
                    'plan_key': i,
                    'targetID': self.orders.get(i)['targetID'],
                    'stopID': self.orders.get(i)['stopID'],
                    'entry_price': self.orders.get(i)['entry_price'], 
                    'qty': self.orders.get(i)['qty'],
                    'target': self.orders.get(i)['target'],
                    'stop': self.orders.get(i)['stop'],
                    'strat': self.orders.get(i)['strat'],
                    'direction': self.orders.get(i)['direction'],
                    'strat_cond': self.orders.get(i)['strat_cond'],
                    'strat_name': self.orders.get(i)['strat_name'],
                    'commission': self.orders.get(i)['commission'] * 2,
                    'margin': self.orders.get(i)['margin'], 
                    'intraday_strat': self.orders.get(i)['intraday_strat'],
                    'events': self.orders.get(i)['events'],


                    'close_price': close_price,
                    'realizedPL': round((close_price-self.orders.get(i)['entry_price']) * self.orders.get(i)['qty'] / self.handle.std_curr(self.orders.get(i)['asset']), 2), 
                    'close_time': last_trade[3],
                    'closingID': last_trade[0]

                }})

                pd.to_pickle(self.trades, f'./DATA/trades/trades_{dt.datetime.now(tz=pytz.timezone("Europe/Moscow")).date()}') 

        except Exception as e:
            logging.error(str(e) + f' errr on add_log with {self.orders.get(i)} \n')
            pass


        
    def close_all(self):

        lt = []

        if len(self.orders.keys()) > 0:

            for i in self.orders.keys():

                if str(self.orders.get(i)['tradeID']) in self.handle.open_positions().keys(): 

                    self.handle.close_order(str(self.orders.get(i)['tradeID']))

                    lt.append((i, self.orders.get(i)['tradeID']))    


        print('waiting to close all')
        time.sleep(30)

        if len(lt) > 0:
            for i in lt:
                self.add_log(i[0], i[1])
                self.orders.pop(i[0])
            pd.to_pickle(self.orders, f'./orders')


        
        print(pd.DataFrame(self.trades.values(), self.trades.keys())[['plan_key', 'asset', 'entry_date', 'entry_price',
                                                                    'close_price', 'entry_time', 'close_time', 'qty', 
                                                                    'intraday_strat', 'realizedPL']])

        print('\n Order Dictionary -> ', 
                        pd.DataFrame(self.orders.values(), self.orders.keys()))

        now = pd.to_timedelta(str(dt.datetime.now(tz=pytz.timezone('Europe/Moscow')).time()))
        next_day = dt.timedelta(hours=23, minutes=59, seconds=59)
        total_wait = next_day - now
        total_wait = (int(str(total_wait).split(' ')[2].split(':')[0]) * 3600) + (int(str(total_wait).split(' ')[2].split(':')[1]) * 60) + 60

        print(f'\n !!! Daily Risk - Reward achieved or End of Day and will resume in {int(total_wait / 60)} minutes !!!')    

        time.sleep(total_wait)

        # import os
        # os._exit(0)



    def order_update(self):

        for i in self.orders.keys():
    
            current_price = self.handle.candle_data(self.orders.get(i)['asset'], 1, 1).close.values[0]

            orderid = self.orders.get(i)['orderID']

            if self.orders.get(i)['tradeID'] == 0:
                
                try:
                    for ii in self.handle.open_positions():

                        if orderid == self.handle.open_positions().get(ii)['orderID']:

                            entry_price = self.handle.open_positions().get(ii)['entry_price']
                            convert = self.handle.std_curr(self.orders.get(i)['asset']) #UP

                            self.orders.get(i).update({

                                    'tradeID': int(self.handle.open_positions().get(ii)['targetID']-1),
                                    'targetID': int(self.handle.open_positions().get(ii)['targetID']),
                                    'stopID': int(self.handle.open_positions().get(ii)['stopID']),
                                    'commission': self.handle.open_positions().get(ii)['commission'],
                                    'entry_time': self.handle.open_positions().get(ii)['entry_time'],
                                    'entry_price': entry_price, 
                                    'current_price': current_price,
                                    'unrealizedPL': round((entry_price - current_price) * self.orders.get(i)['qty'] / convert, 2), #UP
                                    'margin': round(current_price * self.orders.get(i)['qty'] * 0.03 / convert, 2), #UP

                            }) 
                except Exception as e:
                    logging.error(str(e) + ' issue on self.handle.open_positions() inside f(order_update)')
                    pass

            else:

                try:
                    self.orders.get(i).update({

                            'current_price': current_price,
                            'unrealizedPL': round((current_price - self.orders.get(i)['entry_price']) * self.orders.get(i)['qty'] / self.handle.std_curr(self.orders.get(i)['asset']), 2), 

                    })

                except Exception as e:
                    logging.error(str(e) + f'error on orders_update {self.orders.get(i).update} \n')
                    pass

            
            pd.to_pickle(self.orders, f'./orders') 


    def order_mgt(self):

        lt = []

        for i in self.orders.keys():

            if str(self.orders.get(i)['tradeID']) not in self.handle.open_positions().keys(): 
                
                lt.append((i, self.orders.get(i)['tradeID']))

            elif self.check_duration(i):

                self.handle.close_order(str(self.orders.get(i)['tradeID']))

        
        print('\n', pd.DataFrame(self.orders.values(), self.orders.keys())[['plan_key', 'asset', 'current_price', 'entry_date',
                                                                            'entry_price', 'entry_time', 'qty', 'stop', 'stopID',
                                                                            'target', 'targetID', 'tradeID', 'unrealizedPL']])


        if len(lt) > 0:
            for i in lt:
                self.add_log(i[0], i[1])
                self.orders.pop(i[0])
            pd.to_pickle(self.orders, f'./orders') #date_trade



    def day_mgt(self):
        
        if self.orders == {}: 
            orders_pl = 0
        else:
            orders_pl = sum(pd.DataFrame(self.orders.values(), self.orders.keys())['unrealizedPL'])

            self.order_mgt()
            

        if len(self.trades.keys()) > 0: 

            closed_pl = sum(pd.DataFrame(self.trades.values(), self.trades.keys())['realizedPL'])

            print('\n', pd.DataFrame(self.trades.values(), self.trades.keys())[['plan_key', 'asset', 'entry_date', 'entry_price',
                                                                                'close_price', 'entry_time', 'close_time', 'qty', 
                                                                                'intraday_strat', 'realizedPL']])

        else:
            closed_pl = 0
        

        if (orders_pl + closed_pl) < (-1 * daily_risk):
            print(f'START CLOSE_ALL. Open Orders = {orders_pl}, Closed Orders = {closed_pl}, Daily Risk = {daily_risk}')

            self.close_all()

        elif (orders_pl + closed_pl) > (3 * daily_risk):
            print(f'START CLOSE_ALL. Open Orders = {orders_pl}, Closed Orders = {closed_pl}, Daily Risk = {daily_risk}')

            self.close_all()

        

    def exit_calc(self, curr, id, type='day'):
    
        if type == 'day':
            target = (self.plan[id]['profit'][0] / 10) * self.plan[id]['atr']
            stop_price = (self.plan[id]['stop'][0] / 10) * self.plan[id]['atr']

        else:
            target_df = self.handle.candle_data(curr, self.plan[id]['profit'][1], self.plan[id]['profit'][2] + 1)
            target = self.ind.ATR(target_df, self.plan[id]['profit'][2], self.plan[id]['profit'][0])

            stop_df = self.handle.candle_data(curr, self.plan[id]['stop'][1], self.plan[id]['stop'][2] + 1)
            stop_price = self.ind.ATR(stop_df, self.plan[id]['stop'][2], self.plan[id]['stop'][0])

        return target, stop_price


    def condition(self, id, curr): 
        
        strat = self.strat.master(id, self.plan[id]['strat_cond'])

        try:

            if ((self.plan[id]['try_qty'] >= 1) and 
                ((self.current_time() > self.plan[id]['start'] and self.current_time() < self.plan[id]['break_start']) 
                or (self.current_time() < self.plan[id]['end'] and self.current_time() > self.plan[id]['break_end'])) and 
                (self.current_time() > self.handle.trading_hours(curr)[0] and self.current_time() < self.handle.trading_hours(curr)[1]) and
                strat[0] == 'True' and (id not in self.orders.keys())): 

                current_price = self.handle.candle_data(curr, 1, 1).close.values[0] 
                target, stop_price = self.exit_calc(curr, id, self.plan[id]['profit'][3]) 
                digits = self.handle.instruments_info(curr) -1
                size = int(self.handle.std_curr(curr) * (self.plan[id]['size'] / stop_price)) 
                direction = self.plan[id]['direction']

                if direction == 'buy':

                    target = round(target + current_price, digits)
                    stop = round(current_price - stop_price, digits)

                elif direction == 'sell':

                    target = round(current_price - target, digits)
                    stop = round(current_price + stop_price, digits)
                
                if abs(size) >= 1:
                    return self.order_execution(curr, direction, size, target, stop, id, current_price, digits, strat[1])
        
        except Exception as e:
            logging.error(str(e) + ' error on def condition()')
            pass


    def order_execution(self, curr, direction, size, target, stop, id, current_price, digits, strat):
        if direction == 'sell':
            size = -size

        order = self.handle.order(curr, size, target, stop)


        self.plan.get(id).update({
                                'try_qty': self.plan[id]['try_qty'] - 1
                                })

        self.orders.update({id:{
            'asset': curr,
            'entry_date': dt.datetime.now(tz=pytz.timezone("Europe/Moscow")).date(), 
            'entry_time': dt.datetime.now(tz=pytz.timezone("Europe/Moscow")).time(), 
            'orderID': int(order[0].order.orderId),
            'tradeID': 0,
            'targetID': 0,
            'stopID': 0,
            'entry_price': current_price, 
            'current_price': current_price,
            'qty': size,
            'target': target,
            'stop': stop,
            'unrealizedPL': 0,
            'strat': self.plan.get(id)['strat'],
            'direction': self.plan.get(id)['direction'],
            'strat_cond': self.plan.get(id)['strat_cond'],
            'strat_name': self.plan.get(id)['strat_name'],
            'intraday_strat': strat,
            'events': cal_list(dt.datetime.now(tz=pytz.timezone("Europe/Moscow"))),
            'commission': 0
        }})


        pd.to_pickle(self.orders, f'./orders') 

        chart(self.plan, id, curr, (self.current_time()+100), dt.datetime.now(tz=pytz.timezone("Europe/Moscow")).date())

