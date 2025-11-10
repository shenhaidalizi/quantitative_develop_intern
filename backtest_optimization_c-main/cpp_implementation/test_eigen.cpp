#include <iostream>
#include <Eigen/Dense>
using namespace Eigen;
int main() {
    Matrix2d m;
    m << 1, 2, 3, 4;
    std::cout << "矩阵 m:\n" << m << std::endl;
    std::cout << "转置:\n" << m.transpose() << std::endl;
    return 0;
}
