import datetime
import time

"""
일정한 시간 간격별로 코드 실행 필요시 timesleep 이용하면 정확한 간격 유지가 어려우므로
시간을 기준으로 timedelta 시도함.
"""

while True:
    #현재 시간 확보
    timeNow = datetime.datetime.now()
    #반복 주기 시간
    timeDelta = datetime.timedelta(minutes=1)
    #while 탈출 기준
    whileExit = timeNow + timeDelta
    
    n = 0
    while timeNow <= whileExit:
        n += 1
        #현재 시간 update
        timeNow = datetime.datetime.now()
        timeStr = timeNow.strftime('%Y-%m-%d %H:%M:%S')
        print(f'{n:02d} - {timeStr}')
        time.sleep(1)
    
    print('END!')