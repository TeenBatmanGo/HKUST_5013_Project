# -*- coding: utf-8 -*-
"""
Created on Sat Sep 16 16:08:42 2017

@author: MAngO
"""

# Change the working directory to your strategy folder. You should change this 
# directory below on your own computer accordingly
import os
working_directory = '/Users/lingxiaozhang/Desktop/fantasticfour'
os.chdir(working_directory)
from strategy import handle_bar

# Run the main function in your demo.py to get your model and training reday(if there is any)
os.system('python strategy.py')

import h5py
import pandas as pd
import numpy as np
# All data directory
data_directory = '/Users/lingxiaozhang/Desktop/fantasticfour/Data/'
format1_dir = 'data_format1_20170717_20170915.h5'
#format2_dir = 'data_format2_20170717_20170915.h5'
#format2_dir = 'data_format2_20170918_20170922.h5'
#format2_dir = 'data_format2_20170925_20170929.h5'
#format2_dir = 'data_format2_20171009_20171013.h5'
#format2_dir = 'data_format2_20171016_20171020.h5'
#format2_dir = 'data_format2_20171023_20171027.h5'
#format2_dir = 'data_format2_20171030_20171103.h5'
format2_dir = 'data_format2_20171106_20171110.h5'
#format2_dir = 'data_format2_20171113_20171117.h5'

''' In Python, list appending should be careful because it is passed by reference.
    In case a change on original varible may cause changes in other variables, 
    sometimes we need to use copy.deepcopy to make a duplicate.
'''
import copy

# Class of memory for data storage
class memory:
    def __init__(self):
        pass

class backTest:
    def __init__(self):
        # Initialize strategy memory with None. New memory will be updated every minute in backtest
        self.memory = memory()
        
        # Initial setting of backtest
        self.init_cash = 10000000.
        self.margin_threshold = 1000000.
        self.commissionRatio = 0.00005
        
        # Data path
        self.info_path = data_directory+'information.csv'
        self.data_format1_path = data_directory+format1_dir
        self.data_format2_path = data_directory+format2_dir
        
        # You can adjust the path variables below to train and test your own model
        self.train_data_path = ''
        self.test_data_path = ''
    
    def pnl_analyze(self, detailDF_pnl):
        ''' Function that uses pyfolio developed by quantopian to analyze the 
        pnl curve given by the backTest function
        
        Params: total_balance series from detail dataframe generated by backTest
        
        Note: you can get pyfolio package simply by typing 'pip install pyfolio' 
        and enter in your command line tool console. No need to install theano since
        we don't do bayesian analysis here.
        '''
        
        # Get return series from pnl series, and resample return series on a daily basis
        pnl_daily = detailDF_pnl.resample('D').last()
        day_one_return = pnl_daily[0]/self.init_cash - 1.
        pnl_ret_daily = pnl_daily.pct_change()
        pnl_ret_daily[0] = day_one_return
        pnl_ret_daily = pnl_ret_daily.dropna()
        
        # Convert datetime to timezone-aware format and change the timezone to Beijing
        pnl_ret_daily = pnl_ret_daily.tz_localize('UTC').tz_convert('Asia/Shanghai')
        
        # PnL plot, drawdown analysis and risk analysis
        import pyfolio as pf
        # This benchmark(SHY) is the ETF that tracks 1-3 year US treasury bonds, you can also use
        # symbols like SPY for S&P500 or ASHR for CSI300 index
        benchmark = pf.utils.get_symbol_rets('SHY')
        # Generate different reports according to length of backtest
        timeIndex = pnl_ret_daily.index
        if((timeIndex[-1]-timeIndex[0]).days>30):
            pf.create_returns_tear_sheet(pnl_ret_daily, benchmark_rets=benchmark)
        else:
            pf.create_simple_tear_sheet(pnl_ret_daily, benchmark_rets=benchmark)
        
        return pnl_ret_daily
    
    def backTest(self):
        ''' Function that used to do back-test based on the strategy you give
        
        Params: None
        
        Notes: this back-test function will move on minute bar and generate your 
        strategy detail dataframe by using the position matrix your strategy gives
        each minute
        
        Data: 
        1. Load futures information matrix and trading data during backtesting period
        2. You can load different .h5 file by changing the path down below to paths like
        self.train_data_path or self.test_data_path so that you can test and train your
        own strategy on different periods
        3. Try to make your strategy profitable and achieve stable return
        '''
        
        info = pd.read_csv(self.info_path, encoding='utf-8')
        btData = h5py.File(self.data_format2_path, mode='r')
        keys = list(btData.keys())
        
        # PnL initialization
        timer = 0
        pnl = self.init_cash
        details = list()
        detail = [np.repeat(0.,13), self.init_cash, 0., 0., self.init_cash, 0.]
        lastPosition = np.repeat(0, 13)
        
        for i in range(len(keys)-1):
            # Data of current minute and next minute
            data_cur_min = btData[keys[i]][:]
            exe_cur_min = np.mean(data_cur_min[:,:4], axis=1)
            exe_next_min = np.mean(btData[keys[i+1]][:,:4], axis=1)
            
            # Update position and parameter
            [curPosition, self.memory] = handle_bar(timer, data_cur_min, info, self.init_cash, self.commissionRatio, detail, self.memory)
            
            # Calculate margin required and commission charged
            marginRequired = np.matmul(np.abs(curPosition), (exe_next_min * info.unit_per_lot * info.margin_rate))
            transactionVolume = np.matmul(np.abs(curPosition-lastPosition), (exe_next_min * info.unit_per_lot))
            commission = transactionVolume * self.commissionRatio
            
            # Check and update pnl
            dataChange = exe_next_min - exe_cur_min
            revenue_min = np.matmul(lastPosition, dataChange * info.unit_per_lot)
            pnl = pnl + revenue_min - commission
            
            # Check if strategy losses too much
            assert pnl > self.margin_threshold, "Too much loss, strategy failed"
            
            # Check if margin requirement is satisfied
            assert marginRequired <= pnl, "You don't have enough margin"
            
            # Keep record
            detail = [curPosition, pnl-marginRequired, marginRequired, revenue_min, pnl, commission]
            details.append(copy.deepcopy(detail))
            
            # Update position and timer
            lastPosition = copy.deepcopy(curPosition)
            timer+=1
            if '09:30:00' in keys[i]:
                print(keys[i][:10])
            
        detailCol = ["postion","cash_balance", "margin_balance", "revenue", "total_balance", "transaction_cost"]
        detailsDF = pd.DataFrame(details,index=pd.to_datetime(keys[:-1]),columns=detailCol)
        
        btData.close()
        return detailsDF
        
if __name__ == '__main__':
    ''' You can check the details of your strategy and do your own analyze by viewing 
    the strategyDetail dataframe and dailyRet series down below
    '''
    
    bt = backTest()
    strategyDetail = bt.backTest()
    dailyRet = bt.pnl_analyze(strategyDetail.total_balance)

    # Print the summary report of all values needed
    latestinfo = strategyDetail.iloc[-1, :]
    print ("the latest values of position, cash_balance, margin_balance, revenue, total_balance is shown below: ")
    print (latestinfo)

    # Print some statistical values
    print (strategyDetail.describe())