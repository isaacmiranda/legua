// Driver mínimo (fora do repositório): lê casos de stdin e imprime a perda básica do ITM (NTIA) no modo P2P TLS.
// caso: htx hrx f_mhz climate N0 pol eps sigma mdvar time loc sit np step_m e0 e1 ... e(np-1)
#include <cstdio>
#include <vector>
#include "itm.h"
int main() {
  double htx, hrx, f, n0, eps, sig, tm, lo, si, step; int cl, pol, md, np;
  while (scanf("%lf %lf %lf %d %lf %d %lf %lf %d %lf %lf %lf %d %lf", &htx, &hrx, &f, &cl, &n0, &pol, &eps, &sig, &md, &tm, &lo, &si, &np, &step) == 14) {
    std::vector<double> pfl(np + 2); pfl[0] = np - 1; pfl[1] = step;
    for (int i = 0; i < np; i++) scanf("%lf", &pfl[2 + i]);
    double A = 0; long w = 0; int rc = ITM_P2P_TLS(htx, hrx, pfl.data(), cl, n0, f, pol, eps, sig, md, tm, lo, si, &A, &w);
    printf("%d %.4f %ld\n", rc, A, w);
  }
}
