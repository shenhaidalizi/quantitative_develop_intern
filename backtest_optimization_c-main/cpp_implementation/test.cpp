#include <iostream>
#include <Eigen/Dense>
#include <chrono>
#include "multi_weight_backtest.hpp"  // 需要包含两个版本的函数

int main() {
    // -------------------- 测试数据 --------------------
    const int n_timestamps = 100000;  // 时间步数
    const int n_weights = 1000;      // 权重数量

    Eigen::VectorXf prices(n_timestamps);
    Eigen::MatrixXf position_matrix(n_timestamps, n_weights);

    srand((unsigned)time(nullptr));
    for(int i = 0; i < n_timestamps; ++i){
        prices(i) = 10.0f + static_cast<float>(rand()) / RAND_MAX * 10.0f;  // 10~20
        for(int j = 0; j < n_weights; ++j)
            position_matrix(i,j) = rand() % 3 - 1;  // {-1,0,1}
    }

    // // -------------------- 单线程向量化 --------------------
    // auto t1 = std::chrono::high_resolution_clock::now();
    // auto [portfolio_single, cash_single, pos_single] = 
    //     run_multi_weight_vectorized(prices, position_matrix);
    // auto t2 = std::chrono::high_resolution_clock::now();
    // double elapsed_single = std::chrono::duration<double>(t2 - t1).count();
    // std::cout << "单线程向量化耗时: " << elapsed_single << " 秒" << std::endl;


    auto t1 = std::chrono::high_resolution_clock::now();
    auto [portfolio_parallel, cash_parallel, pos_parallel] = 
        run_multi_weight_vectorized_eigen(prices, position_matrix);
    auto t2 = std::chrono::high_resolution_clock::now();
    double elapsed_parallel = std::chrono::duration<double>(t2 - t1).count();
    std::cout << "1耗时: " << elapsed_parallel << " 秒" << std::endl;

    // -------------------- 并行向量化 --------------------
    t1 = std::chrono::high_resolution_clock::now();
    auto [portfolio_parallel_2, cash_parallel_2, pos_parallel_2] = 
        run_multi_weight_vectorized_parallel_2(prices, position_matrix);
    t2 = std::chrono::high_resolution_clock::now();
    elapsed_parallel = std::chrono::duration<double>(t2 - t1).count();
    std::cout << "2耗时: " << elapsed_parallel << " 秒" << std::endl;

    // -------------------- 并行向量化 --------------------
    

    // -------------------- 最大误差对比 --------------------
    float max_diff_portfolio = (portfolio_parallel - portfolio_parallel_2).cwiseAbs().maxCoeff();
    float max_diff_cash      = (cash_parallel - cash_parallel_2).cwiseAbs().maxCoeff();
    float max_diff_pos       = (pos_parallel - pos_parallel_2).cwiseAbs().maxCoeff();

    std::cout << "\n最大误差对比:\n";
    std::cout << "  portfolio 最大差值: " << max_diff_portfolio << "\n";
    std::cout << "  cash 最大差值: "      << max_diff_cash << "\n";
    std::cout << "  position 最大差值: "  << max_diff_pos << "\n";

    return 0;
}
