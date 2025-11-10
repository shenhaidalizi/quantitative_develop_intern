#pragma once
#ifndef EIGEN_USE_MKL_ALL
#define EIGEN_USE_MKL_ALL
#endif

#include <Eigen/Dense>
#include <tuple>
#include <string>
#include <fstream>
#include <cmath>
#include <omp.h>
#include <chrono>
#include <iostream>

using namespace Eigen;


// -------------------- 函数声明 --------------------
// 基于 Eigen 向量化 API 的多权重回测（尽量使用 Eigen 运算替代显式循环）
std::tuple<MatrixXf, MatrixXf, MatrixXf>
run_multi_weight_vectorized_eigen(
    const VectorXf& prices,
    const MatrixXf& position_matrix,
    float initial_cash = 1000000.0,
    std::string trade_mode = "portfolio_pct",
    float max_allocation_pct = 0.5,
    float fixed_cash_amount = 100000.0,
    float position_size = 100.0
);
std::tuple<MatrixXf, MatrixXf, MatrixXf>
run_multi_weight_vectorized_parallel_1(
    const VectorXf& prices,
    const MatrixXf& position_matrix,
    float initial_cash = 1000000.0,
    std::string trade_mode = "portfolio_pct",
    float max_allocation_pct = 0.5,
    float fixed_cash_amount = 100000.0,
    float position_size = 100.0
);
//并行多权重回测函数
std::tuple<MatrixXf, MatrixXf, MatrixXf> 
run_multi_weight_vectorized_parallel_2(
    const VectorXf& prices,
    const MatrixXf& position_matrix,
    float initial_cash = 1000000.0,
    std::string trade_mode = "portfolio_pct",
    float max_allocation_pct = 0.5,
    float fixed_cash_amount = 100000.0,
    float position_size = 100.0
);
// std::tuple<MatrixXf, MatrixXf, MatrixXf> 
// run_multi_weight_vectorized_parallel(
//     const VectorXf& prices,
//     const MatrixXf& position_matrix,
//     float initial_cash = 1000000.0,
//     TradeMode trade_mode = TradeMode::PORTFOLIO_PCT,
//     float max_allocation_pct = 0.5,
//     float fixed_cash_amount = 100000.0,
//     float position_size = 100.0
// );
// 保存矩阵为 CSV 文件
inline void save_matrix_csv(const MatrixXf& mat, const std::string& filename){
    std::ofstream file(filename);
    for(int i=0; i<mat.rows(); ++i){
        for(int j=0; j<mat.cols(); ++j){
            file << mat(i,j);
            if(j < mat.cols()-1) file << ",";
        }
        file << "\n";
    }
}

//
// 单线程多权重回测函数（原始版本，用于验证并行计算）
inline std::tuple<MatrixXf, MatrixXf, MatrixXf> 
run_multi_weight_vectorized(
    const VectorXf& prices,
    const MatrixXf& position_matrix,
    float initial_cash = 1000000.0,
    std::string trade_mode = "portfolio_pct",
    float max_allocation_pct = 0.5,
    float fixed_cash_amount = 100000.0,
    float position_size = 100.0
){
    int n_timestamps = prices.size();
    int n_weights = position_matrix.cols();

    MatrixXf cash_matrix = MatrixXf::Zero(n_timestamps, n_weights);
    MatrixXf real_position_matrix = MatrixXf::Zero(n_timestamps, n_weights);
    MatrixXf portfolio_value_matrix = MatrixXf::Zero(n_timestamps, n_weights);

    // 初始化第一行
    cash_matrix.row(0).array() = initial_cash;
    portfolio_value_matrix.row(0).array() = initial_cash;

    // 计算持仓变化矩阵
    MatrixXf position_change_matrix(n_timestamps, n_weights);
    position_change_matrix.row(0) = position_matrix.row(0);
    for(int i=1; i<n_timestamps; ++i)
        position_change_matrix.row(i) = position_matrix.row(i) - position_matrix.row(i-1);

    // 遍历时间步
    for(int idx=1; idx<n_timestamps; ++idx){
        cash_matrix.row(idx) = cash_matrix.row(idx-1);
        real_position_matrix.row(idx) = real_position_matrix.row(idx-1);

        VectorXf buys = (position_change_matrix.row(idx).array() > 0).cast<float>();
        VectorXf sells = (position_change_matrix.row(idx).array() < 0).cast<float>();

        float price = prices(idx);

        // ----------------- 买入 -----------------
        if(buys.sum() > 0){
            VectorXf buy_positions(n_weights);
            buy_positions.setZero();

            if(trade_mode == "fixed"){
                buy_positions.array() = position_size;
            } else if(trade_mode == "cash_all"){
                for(int w=0; w<n_weights; ++w)
                    buy_positions(w) = std::floor(cash_matrix(idx, w) / price);
            } else if(trade_mode == "portfolio_pct"){
                for(int w=0; w<n_weights; ++w){
                    float portfolio_value = cash_matrix(idx, w) + real_position_matrix(idx, w) * price;
                    float max_pos = std::floor(portfolio_value * max_allocation_pct / price);
                    buy_positions(w) = std::max(0.0f, std::min(max_pos - real_position_matrix(idx, w),
                                                               std::floor(cash_matrix(idx, w) / price)));
                }
            } else if(trade_mode == "fixed_cash"){
                for(int w=0; w<n_weights; ++w)
                    buy_positions(w) = std::floor(fixed_cash_amount / price);
            }

            // 只对买入信号生效
            for(int w=0; w<n_weights; ++w){
                if(buys(w) > 0){
                    float max_affordable = std::floor(cash_matrix(idx, w) / price);
                    buy_positions(w) = std::min(buy_positions(w), max_affordable);
                    float cost = buy_positions(w) * price;
                    cash_matrix(idx, w) -= cost;
                    real_position_matrix(idx, w) += buy_positions(w);
                } else {
                    buy_positions(w) = 0;
                }
            }
        }

        // ----------------- 卖出 -----------------
        if(sells.sum() > 0){
            for(int w=0; w<n_weights; ++w){
                if(sells(w) > 0){
                    float sell_volume = real_position_matrix(idx-1, w);
                    float revenue = sell_volume * price;
                    cash_matrix(idx, w) += revenue;
                    real_position_matrix(idx, w) = 0;
                }
            }
        }

        // ----------------- 更新组合价值 -----------------
        for(int w=0; w<n_weights; ++w)
            portfolio_value_matrix(idx, w) = cash_matrix(idx, w) + real_position_matrix(idx, w) * price;
    }

    return std::make_tuple(portfolio_value_matrix, cash_matrix, real_position_matrix);
}




// //-------------------- 函数定义 --------------------
// inline std::tuple<MatrixXf, MatrixXf, MatrixXf> 
// run_multi_weight_vectorized_parallel_1(
//     const VectorXf& prices,
//     const MatrixXf& position_matrix,
//     float initial_cash,
//     std::string trade_mode,
//     float max_allocation_pct,
//     float fixed_cash_amount,
//     float position_size
// ){
//     int n_timestamps = prices.size();
//     int n_weights = position_matrix.cols();

//     MatrixXf cash_matrix = MatrixXf::Constant(n_timestamps, n_weights, initial_cash);
//     MatrixXf real_position_matrix = MatrixXf::Zero(n_timestamps, n_weights);
//     MatrixXf portfolio_value_matrix = MatrixXf::Constant(n_timestamps, n_weights, initial_cash);

//     // 持仓变化矩阵
//     MatrixXf position_change_matrix(n_timestamps, n_weights);
//     position_change_matrix.row(0) = position_matrix.row(0);
//     for(int i=1; i<n_timestamps; ++i)
//         position_change_matrix.row(i) = position_matrix.row(i) - position_matrix.row(i-1);

//     for(int idx=1; idx<n_timestamps; ++idx){
//         cash_matrix.row(idx) = cash_matrix.row(idx-1);
//         real_position_matrix.row(idx) = real_position_matrix.row(idx-1);

//         Eigen::ArrayXf buys = (position_change_matrix.row(idx).array() > 0).cast<float>();
//         Eigen::ArrayXf sells = (position_change_matrix.row(idx).array() < 0).cast<float>();

//         // ----------------- 买入 -----------------
//         if(buys.sum() > 0){
//             Eigen::ArrayXf buy_positions = Eigen::ArrayXf::Zero(n_weights);

//             #pragma omp parallel for
//             for(int w=0; w<n_weights; ++w){
//                 if(buys(w) == 0) continue;

//                 if(trade_mode == "fixed")
//                     buy_positions(w) = position_size;
//                 else if(trade_mode == "cash_all")
//                     buy_positions(w) = std::floor(cash_matrix(idx, w) / prices(idx));
//                 else if(trade_mode == "portfolio_pct"){
//                     float portfolio_value = cash_matrix(idx, w) + real_position_matrix(idx, w) * prices(idx);
//                     float max_pos = std::floor(portfolio_value * max_allocation_pct / prices(idx));
//                     buy_positions(w) = std::max(0.0f, std::min(max_pos - real_position_matrix(idx, w),
//                                                                std::floor(cash_matrix(idx, w) / prices(idx))));
//                 }
//                 else if(trade_mode == "fixed_cash")
//                     buy_positions(w) = std::floor(fixed_cash_amount / prices(idx));

//                 float max_affordable = std::floor(cash_matrix(idx, w) / prices(idx));
//                 buy_positions(w) = std::min(buy_positions(w), max_affordable);

//                 float cost = buy_positions(w) * prices(idx);
//                 #pragma omp atomic
//                 cash_matrix(idx, w) -= cost;
//                 #pragma omp atomic
//                 real_position_matrix(idx, w) += buy_positions(w);
//             }
//         }

//         // ----------------- 卖出 -----------------
//         if(sells.sum() > 0){
//             #pragma omp parallel for
//             for(int w=0; w<n_weights; ++w){
//                 if(sells(w) == 0) continue;
//                 float sell_volume = real_position_matrix(idx-1, w);
//                 float revenue = sell_volume * prices(idx);
//                 #pragma omp atomic
//                 cash_matrix(idx, w) += revenue;
//                 #pragma omp atomic
//                 real_position_matrix(idx, w) -= sell_volume;
//             }
//         }

//         // ----------------- 更新组合价值 -----------------
//         #pragma omp parallel for
//         for(int w=0; w<n_weights; ++w){
//             portfolio_value_matrix(idx, w) = cash_matrix(idx, w) + real_position_matrix(idx, w) * prices(idx);
//         }
//     }

//     return std::make_tuple(portfolio_value_matrix, cash_matrix, real_position_matrix);
// }


// -------------------- 函数定义 --------------------
// inline std::tuple<MatrixXf, MatrixXf, MatrixXf> 
// run_multi_weight_vectorized_parallel(
//     const VectorXf& prices,
//     const MatrixXf& position_matrix,
//     float initial_cash,
//     std::string trade_mode,
//     float max_allocation_pct,
//     float fixed_cash_amount,
//     float position_size
// ){
//     int n_timestamps = prices.size();
//     int n_weights = position_matrix.cols();

//     MatrixXf cash_matrix = MatrixXf::Constant(n_timestamps, n_weights, initial_cash);
//     MatrixXf real_position_matrix = MatrixXf::Zero(n_timestamps, n_weights);
//     MatrixXf portfolio_value_matrix = MatrixXf::Constant(n_timestamps, n_weights, initial_cash);

//     // 计算持仓变化矩阵
//     MatrixXf position_change_matrix(n_timestamps, n_weights);
//     position_change_matrix.row(0) = position_matrix.row(0);
//     for(int i=1; i<n_timestamps; ++i)
//         position_change_matrix.row(i) = position_matrix.row(i) - position_matrix.row(i-1);

//     // ------------------ 并行处理时间步 ------------------
//     #pragma omp parallel for schedule(static)
//     for(int idx=1; idx<n_timestamps; ++idx){
//         // 拷贝前一行
//         cash_matrix.row(idx) = cash_matrix.row(idx-1);
//         real_position_matrix.row(idx) = real_position_matrix.row(idx-1);

//         const float price = prices(idx);

//         for(int w=0; w<n_weights; ++w){
//             float pos_change = position_change_matrix(idx, w);

//             // 买入
//             if(pos_change > 0){
//                 float buy_qty = 0;
//                 if(trade_mode == "fixed")
//                     buy_qty = position_size;
//                 else if(trade_mode == "cash_all")
//                     buy_qty = std::floor(cash_matrix(idx, w) / price);
//                 else if(trade_mode == "portfolio_pct"){
//                     float portfolio_value = cash_matrix(idx, w) + real_position_matrix(idx, w) * price;
//                     float max_pos = std::floor(portfolio_value * max_allocation_pct / price);
//                     buy_qty = std::max(0.0f, std::min(max_pos - real_position_matrix(idx, w),
//                                                      std::floor(cash_matrix(idx, w) / price)));
//                 } else if(trade_mode == "fixed_cash")
//                     buy_qty = std::floor(fixed_cash_amount / price);

//                 float max_affordable = std::floor(cash_matrix(idx, w) / price);
//                 buy_qty = std::min(buy_qty, max_affordable);

//                 cash_matrix(idx, w) -= buy_qty * price;
//                 real_position_matrix(idx, w) += buy_qty;
//             }

//             // 卖出
//             else if(pos_change < 0){
//                 float sell_qty = real_position_matrix(idx-1, w);
//                 cash_matrix(idx, w) += sell_qty * price;
//                 real_position_matrix(idx, w) = 0;
//             }

//             // 更新组合价值
//             portfolio_value_matrix(idx, w) = cash_matrix(idx, w) + real_position_matrix(idx, w) * price;
//         }
//     }

//     return std::make_tuple(portfolio_value_matrix, cash_matrix, real_position_matrix);
// }

// (可用版本)-------------------- 函数定义 --------------------
// inline std::tuple<MatrixXf, MatrixXf, MatrixXf>
// run_multi_weight_vectorized_parallel_1(
//     const VectorXf& prices,
//     const MatrixXf& position_matrix,
//     float initial_cash,
//     std::string trade_mode,
//     float max_allocation_pct,
//     float fixed_cash_amount,
//     float position_size
// ){
//     int n_timestamps = prices.size();
//     int n_weights = position_matrix.cols();

//     MatrixXf cash_matrix = MatrixXf::Constant(n_timestamps, n_weights, initial_cash);
//     MatrixXf real_position_matrix = MatrixXf::Zero(n_timestamps, n_weights);
//     MatrixXf portfolio_value_matrix = MatrixXf::Constant(n_timestamps, n_weights, initial_cash);

//     // 计算持仓变化矩阵
//     MatrixXf position_change_matrix(n_timestamps, n_weights);
//     position_change_matrix.row(0) = position_matrix.row(0);
//     for(int i=1; i<n_timestamps; ++i)
//         position_change_matrix.row(i) = position_matrix.row(i) - position_matrix.row(i-1);

//     // ------------------ 时间步串行，列并行 ------------------
//     for(int idx=1; idx<n_timestamps; ++idx){
//         cash_matrix.row(idx) = cash_matrix.row(idx-1);
//         real_position_matrix.row(idx) = real_position_matrix.row(idx-1);

//         const float price = prices(idx);

//         #pragma omp parallel for schedule(static)
//         for(int w=0; w<n_weights; ++w){
//             float pos_change = position_change_matrix(idx, w);

//             // ----------------- 买入 -----------------
//             if(pos_change > 0){
//                 float buy_qty = 0;
//                 if(trade_mode == "fixed")
//                     buy_qty = position_size;
//                 else if(trade_mode == "cash_all")
//                     buy_qty = std::floor(cash_matrix(idx, w) / price);
//                 else if(trade_mode == "portfolio_pct"){
//                     float portfolio_value = cash_matrix(idx, w) + real_position_matrix(idx, w) * price;
//                     float max_pos = std::floor(portfolio_value * max_allocation_pct / price);
//                     buy_qty = std::max(0.0f, std::min(max_pos - real_position_matrix(idx, w),
//                                                      std::floor(cash_matrix(idx, w) / price)));
//                 } else if(trade_mode == "fixed_cash")
//                     buy_qty = std::floor(fixed_cash_amount / price);

//                 float max_affordable = std::floor(cash_matrix(idx, w) / price);
//                 buy_qty = std::min(buy_qty, max_affordable);

//                 cash_matrix(idx, w) -= buy_qty * price;
//                 real_position_matrix(idx, w) += buy_qty;
//             }

//             // ----------------- 卖出 -----------------
//             else if(pos_change < 0){
//                 float sell_qty = real_position_matrix(idx-1, w);
//                 cash_matrix(idx, w) += sell_qty * price;
//                 real_position_matrix(idx, w) = 0;
//             }

//             // ----------------- 更新组合价值 -----------------
//             portfolio_value_matrix(idx, w) = cash_matrix(idx, w) + real_position_matrix(idx, w) * price;
//         }
//     }

//     return std::make_tuple(portfolio_value_matrix, cash_matrix, real_position_matrix);
// }

// inline std::tuple<MatrixXf, MatrixXf, MatrixXf>
// run_multi_weight_vectorized_parallel_2(
//     const VectorXf& prices,
//     const MatrixXf& position_matrix,
//     float initial_cash,
//     std::string trade_mode,
//     float max_allocation_pct,
//     float fixed_cash_amount,
//     float position_size
// ){
//     int n_timestamps = prices.size();
//     int n_weights = position_matrix.cols();

//     MatrixXf cash_matrix = MatrixXf::Constant(n_timestamps, n_weights, initial_cash);
//     MatrixXf real_position_matrix = MatrixXf::Zero(n_timestamps, n_weights);
//     MatrixXf portfolio_value_matrix = MatrixXf::Constant(n_timestamps, n_weights, initial_cash);

//     // 计算持仓变化矩阵
//     MatrixXf position_change_matrix(n_timestamps, n_weights);
//     position_change_matrix.row(0) = position_matrix.row(0);
//     for(int i=1; i<n_timestamps; i+=2){
//         position_change_matrix.row(i) = position_matrix.row(i) - position_matrix.row(i-1);
//         position_change_matrix.row(i + 1) = position_matrix.row(i + 1) - position_matrix.row(i);
//     }
    
        
//     // ------------------ 时间步串行，列并行 ------------------
//     for(int idx=1; idx<n_timestamps; ++idx){
//         cash_matrix.row(idx) = cash_matrix.row(idx-1);
//         real_position_matrix.row(idx) = real_position_matrix.row(idx-1);

//         const float price = prices(idx);

//         #pragma omp parallel for schedule(static)
//         for(int w=0; w<n_weights; ++w){
//             float pos_change = position_change_matrix(idx, w);

//             // ----------------- 买入 -----------------
//             if(pos_change > 0){
//                 float buy_qty = 0;
//                 if(trade_mode == "fixed")
//                     buy_qty = position_size;
//                 else if(trade_mode == "cash_all")
//                     buy_qty = std::floor(cash_matrix(idx, w) / price);
//                 else if(trade_mode == "portfolio_pct"){
//                     float portfolio_value = cash_matrix(idx, w) + real_position_matrix(idx, w) * price;
//                     float max_pos = std::floor(portfolio_value * max_allocation_pct / price);
//                     buy_qty = std::max(0.0f, std::min(max_pos - real_position_matrix(idx, w),
//                                                      std::floor(cash_matrix(idx, w) / price)));
//                 } else if(trade_mode == "fixed_cash")
//                     buy_qty = std::floor(fixed_cash_amount / price);

//                 float max_affordable = std::floor(cash_matrix(idx, w) / price);
//                 buy_qty = std::min(buy_qty, max_affordable);

//                 cash_matrix(idx, w) -= buy_qty * price;
//                 real_position_matrix(idx, w) += buy_qty;
//             }

//             // ----------------- 卖出 -----------------
//             else if(pos_change < 0){
//                 float sell_qty = real_position_matrix(idx-1, w);
//                 cash_matrix(idx, w) += sell_qty * price;
//                 real_position_matrix(idx, w) = 0;
//             }

//             // ----------------- 更新组合价值 -----------------
//             portfolio_value_matrix(idx, w) = cash_matrix(idx, w) + real_position_matrix(idx, w) * price;
//         }
//     }

//     return std::make_tuple(portfolio_value_matrix, cash_matrix, real_position_matrix);
// }

inline std::tuple<MatrixXf, MatrixXf, MatrixXf> 
run_multi_weight_vectorized_parallel_1(
    const VectorXf& prices,
    const MatrixXf& position_matrix,
    float initial_cash,
    std::string trade_mode,
    float max_allocation_pct,
    float fixed_cash_amount,
    float position_size
){
    auto t0 = std::chrono::high_resolution_clock::now();
    //获取时间步数和权重数量
    int n_timestamps = prices.size();
    int n_weights = position_matrix.cols();
    
    MatrixXf cash_matrix = MatrixXf::Zero(n_timestamps, n_weights);  // 现金矩阵
    cash_matrix.row(0).setConstant(initial_cash);
    
    MatrixXf real_position_matrix = MatrixXf::Zero(n_timestamps, n_weights);  // 实际持仓矩阵
    MatrixXf portfolio_value_matrix = MatrixXf::Zero(n_timestamps, n_weights);  // 组合价值矩阵
    portfolio_value_matrix.row(0).setConstant(initial_cash);

    // 缓冲区（优化性能） - 统一使用 Array 进行逐元素运算（行向 1 x n_weights）
    ArrayXXf pos_change(1, n_weights); pos_change.setZero();
    ArrayXXf buy_qty(1, n_weights); buy_qty.setZero();
    ArrayXXf max_afford(1, n_weights); max_afford.setZero();
    ArrayXXf tmp(1, n_weights); tmp.setZero();
    auto t1 = std::chrono::high_resolution_clock::now();
    std::cout << "[耗时] 矩阵初始化: " 
              << std::chrono::duration<double>(t1 - t0).count() << " 秒" << std::endl;
              
    // // 计算持仓变化矩阵 (首行等于初始持仓，后续为逐行差分)
    // MatrixXf position_change_matrix(n_timestamps, n_weights);
    // position_change_matrix.row(0) = position_matrix.row(0);

    // // 使用逐列差分 (避免使用 block 或者创建临时矩阵)
    // if(n_timestamps > 1){
    //     position_change_matrix.block(1, 0, n_timestamps - 1, n_weights) =
    //         position_matrix.block(1, 0, n_timestamps - 1, n_weights) -
    //         position_matrix.block(0, 0, n_timestamps - 1, n_weights);
    // }




    auto t2 = std::chrono::high_resolution_clock::now();
    std::cout << "[耗时] 计算 position_change_matrix: "
            << std::chrono::duration<double>(t2 - t1).count() << " 秒" << std::endl;
    const int unroll_factor = 4;

    // ------------------ 时间步串行，列并行 + 循环展开 ------------------
    auto t_loop_start = std::chrono::high_resolution_clock::now();
    for(int idx=1; idx<n_timestamps; ++idx){
         // 继承上一行的现金和持仓
         cash_matrix.row(idx) = cash_matrix.row(idx - 1);
         real_position_matrix.row(idx) = real_position_matrix.row(idx - 1);

        // 本行持仓变化（买卖信号）
        pos_change = (position_matrix.row(idx) - position_matrix.row(idx - 1)).array();

        // 买入和卖出掩码（布尔数组）
        Array<bool, Dynamic, Dynamic> buys_mask = (pos_change > 0.0f);
        Array<bool, Dynamic, Dynamic> sells_mask = (pos_change < 0.0f);

        bool has_buys = buys_mask.any();
        bool has_sells = sells_mask.any();
        float price32 = prices(idx);

        if (has_buys) {
            // 组合价值与最大仓位
            tmp = real_position_matrix.row(idx).array() * price32;
            tmp += cash_matrix.row(idx).array();  // 组合总值
            buy_qty = (tmp * max_allocation_pct / price32).floor();
            buy_qty -= real_position_matrix.row(idx).array();
            max_afford = (cash_matrix.row(idx).array() / price32).floor();
            buy_qty = buy_qty.max(0.0f).min(max_afford);

            // 仅对买入信号生效
            buy_qty *= buys_mask.cast<float>();
            cash_matrix.row(idx).array() -= buy_qty * price32;  // 更新现金
            real_position_matrix.row(idx).array() += buy_qty;   // 更新持仓
        }

        // 卖出逻辑
        if (has_sells) {
            ArrayXXf sell_qty = real_position_matrix.row(idx - 1).array() * sells_mask.cast<float>();
            cash_matrix.row(idx).array() += sell_qty * price32;  // 更新现金
            real_position_matrix.row(idx).array() -= sell_qty;   // 更新持仓
        }

        // 组合价值更新
        portfolio_value_matrix.row(idx).array() =
            cash_matrix.row(idx).array() + real_position_matrix.row(idx).array() * price32;  // 组合价值
    }
    auto t3 = std::chrono::high_resolution_clock::now();
    std::cout << "[耗时] 主循环总耗时: "
              << std::chrono::duration<double>(t3 - t_loop_start).count() << " 秒" << std::endl;
    return std::make_tuple(portfolio_value_matrix, cash_matrix, real_position_matrix);
}

inline std::tuple<MatrixXf, MatrixXf, MatrixXf>
run_multi_weight_vectorized_parallel_2(
    const VectorXf& prices,
    const MatrixXf& position_matrix,
    float initial_cash,
    std::string trade_mode,
    float max_allocation_pct,
    float fixed_cash_amount,
    float position_size
){
    auto t0 = std::chrono::high_resolution_clock::now();

    int n_timestamps = prices.size();
    int n_weights = position_matrix.cols();

    MatrixXf cash_matrix(n_timestamps, n_weights);
    cash_matrix.row(0).array() = initial_cash;

    MatrixXf real_position_matrix = MatrixXf::Zero(n_timestamps, n_weights);

    MatrixXf portfolio_value_matrix(n_timestamps, n_weights);
    portfolio_value_matrix.row(0).array() = initial_cash;

    auto t1 = std::chrono::high_resolution_clock::now();
    std::cout << "[耗时] 矩阵初始化: " 
              << std::chrono::duration<double>(t1 - t0).count() << " 秒" << std::endl;

    // 计算持仓变化矩阵
    MatrixXf position_change_matrix(n_timestamps, n_weights);
    position_change_matrix.row(0) = position_matrix.row(0);
    position_change_matrix.block(1, 0, n_timestamps-1, n_weights) = 
        position_matrix.block(1, 0, n_timestamps-1, n_weights) - 
        position_matrix.block(0, 0, n_timestamps-1, n_weights);

    auto t2 = std::chrono::high_resolution_clock::now();
    std::cout << "[耗时] 计算 position_change_matrix: "
              << std::chrono::duration<double>(t2 - t1).count() << " 秒" << std::endl;

    const int unroll_factor = 4;

    // ------------------ 时间步串行，列并行 + 循环展开 ------------------
    auto t_loop_start = std::chrono::high_resolution_clock::now();
    for(int idx=1; idx<n_timestamps; ++idx){
        cash_matrix.row(idx) = cash_matrix.row(idx-1);
        real_position_matrix.row(idx) = real_position_matrix.row(idx-1);

        const float price = prices(idx);

        #pragma omp parallel for schedule(static)
        for(int w=0; w<n_weights; w += unroll_factor){
            for(int u = 0; u < unroll_factor; ++u){
                int col = w + u;
                if(col >= n_weights) break;

                float pos_change = position_change_matrix(idx, col);

        // ----------------- 买入 -----------------
                if(pos_change > 0){
                    float buy_qty = 0;
                    if(trade_mode == "fixed")
                        buy_qty = position_size;
                    else if(trade_mode == "cash_all")
                        buy_qty = std::floor(cash_matrix(idx, col) / price);
                    else if(trade_mode == "portfolio_pct"){
                        float portfolio_value = cash_matrix(idx, col) + real_position_matrix(idx, col) * price;
                        float max_pos = std::floor(portfolio_value * max_allocation_pct / price);
                        buy_qty = std::max(0.0f, std::min(max_pos - real_position_matrix(idx, col),
                                                          std::floor(cash_matrix(idx, col) / price)));
                    } else if(trade_mode == "fixed_cash")
                        buy_qty = std::floor(fixed_cash_amount / price);

                    float max_affordable = std::floor(cash_matrix(idx, col) / price);
                    buy_qty = std::min(buy_qty, max_affordable);

                    // 使用 noalias() 避免临时矩阵
                    cash_matrix(idx, col) -= buy_qty * price;
                    real_position_matrix(idx, col) += buy_qty;
                }

                // ----------------- 卖出 -----------------
                else if(pos_change < 0){
                    float sell_qty = real_position_matrix(idx-1, col);
                    cash_matrix(idx, col) += sell_qty * price;
                    real_position_matrix(idx, col) = 0;
                }

                // ----------------- 更新组合价值 -----------------
                portfolio_value_matrix(idx, col) = cash_matrix(idx, col) + real_position_matrix(idx, col) * price;
            }
        }

        // 每 1000 步打印一次进度和耗时
        // if(idx % 1000 == 0){
        //     auto t_now = std::chrono::high_resolution_clock::now();
        //     std::cout << "[进度] 时间步 " << idx 
        //               << ", 已耗时 " 
        //               << std::chrono::duration<double>(t_now - t_loop_start).count() 
        //               << " 秒" << std::endl;
        // }
    }
    auto t3 = std::chrono::high_resolution_clock::now();
    std::cout << "[耗时] 主循环总耗时: "
              << std::chrono::duration<double>(t3 - t_loop_start).count() << " 秒" << std::endl;

    return std::make_tuple(portfolio_value_matrix, cash_matrix, real_position_matrix);
}

inline std::tuple<MatrixXf, MatrixXf, MatrixXf> 
run_multi_weight_vectorized_eigen(
    const VectorXf& prices,  // 价格序列 (n_timestamps,)
    const MatrixXf& position_matrix,  // 持仓矩阵 (n_timestamps, n_weights)
    float initial_cash,  // 初始现金
    std::string trade_mode,  // 默认交易模式为 portfolio_pct
    float max_allocation_pct,  // 最大仓位比例
    float fixed_cash_amount,  // 固定现金金额
    float position_size  // 固定仓位大小
) {
    int n_timestamps = prices.size();
    int n_weights = position_matrix.cols();

    // 初始化输出矩阵
    MatrixXf cash_matrix = MatrixXf::Zero(n_timestamps, n_weights);  // 现金矩阵
    MatrixXf real_position_matrix = MatrixXf::Zero(n_timestamps, n_weights);  // 实际持仓矩阵
    MatrixXf portfolio_value_matrix = MatrixXf::Zero(n_timestamps, n_weights);  // 组合价值矩阵

    // 初始化第一行
    cash_matrix.row(0).setConstant(initial_cash);
    portfolio_value_matrix.row(0).setConstant(initial_cash);

    // 向量化处理所有时间点
    for (int idx = 1; idx < n_timestamps; ++idx) {
        // 继承上一行的现金和持仓
        cash_matrix.row(idx) = cash_matrix.row(idx - 1);
        real_position_matrix.row(idx) = real_position_matrix.row(idx - 1);

        // 本行持仓变化（买卖信号）
        Array<float, 1, Dynamic> pos_change = (position_matrix.row(idx) - position_matrix.row(idx - 1)).array();

        // 买入和卖出掩码
        Array<bool, 1, Dynamic> buys_mask = (pos_change > 0.0f);
        Array<bool, 1, Dynamic> sells_mask = (pos_change < 0.0f);

        bool has_buys = buys_mask.any();
        bool has_sells = sells_mask.any();
        float price32 = prices(idx);

        // 买入逻辑
        if (has_buys) {
            Array<float, 1, Dynamic> buy_qty(1, n_weights);
            buy_qty.setZero();
            if (trade_mode == "fixed"){
                buy_qty.setConstant(position_size);
            } else if (trade_mode == "cash_all"){
                buy_qty = (cash_matrix.row(idx).array() / price32).floor();
            } else if (trade_mode == "portfolio_pct"){
                Array<float, 1, Dynamic> portfolio_val = cash_matrix.row(idx).array() + real_position_matrix.row(idx).array() * price32;
                Array<float, 1, Dynamic> max_pos = (portfolio_val * max_allocation_pct / price32).floor();
                buy_qty = (max_pos - real_position_matrix.row(idx).array())
                              .max(0.0f)
                              .min((cash_matrix.row(idx).array() / price32).floor());
            } else if (trade_mode == "fixed_cash"){
                buy_qty.setConstant(std::floor(fixed_cash_amount / price32));
            } else {
                buy_qty.setConstant(position_size);
            }

            // 仅对买入信号生效
            buy_qty *= buys_mask.cast<float>();

            // 现金上限再约束一次
            Array<float, 1, Dynamic> max_afford = (cash_matrix.row(idx).array() / price32).floor();
            buy_qty = buy_qty.min(max_afford);

            // 更新现金与持仓
            cash_matrix.row(idx).array() -= buy_qty * price32;
            real_position_matrix.row(idx).array() += buy_qty;
        }

        // 卖出逻辑
        if (has_sells) {
            Array<float, 1, Dynamic> sell_qty = real_position_matrix.row(idx - 1).array() * sells_mask.cast<float>();
            cash_matrix.row(idx).array() += sell_qty * price32;  // 更新现金
            real_position_matrix.row(idx).array() -= sell_qty;   // 更新持仓
        }

        // 组合价值更新
        portfolio_value_matrix.row(idx).array() =
            cash_matrix.row(idx).array() + real_position_matrix.row(idx).array() * price32;
    }

    return std::make_tuple(portfolio_value_matrix, cash_matrix, real_position_matrix);
}

