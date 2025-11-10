编译指令
g++ -O3 -std=c++17 -fopenmp -DNDEBUG -march=native -mavx2 -mfma -DEIGEN_USE_MKL_ALL     test.cpp -I /usr/include/eigen3 -I /usr/include/mkl -L /usr/lib/x86_64-linux-gnu -lmkl_rt -o backtest
运行指令
./backtest 