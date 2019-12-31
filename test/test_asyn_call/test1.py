import multiprocessing
from multiprocessing import Pool, freeze_support, Process
import time

multiprocessing.freeze_support()



def task(pid):
    # do something
    time.sleep(pid)
    return pid

def sleepX(sec:int):
    time.sleep(sec)
    print("wakeup")

def main():
    pool = multiprocessing.Pool(multiprocessing.cpu_count())

    class A:
        def __init__(self):
            self.b = B(self,sleepX)


    class B:
        def __init__(self, a: A,func):
            self.a = a
            self.func = func

        def asyn_call(self):
            pool.apply(
                func=self.func,
                args=[3, ],
                # callback=self.wakeup,
            )
        @staticmethod
        def sleep(i: int):
            print("sleep")
            time.sleep(i)

        def wakeup(self):
            print("wakeup")

    a = A()
    a.b.asyn_call()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()