import torch, time

device = 'cuda'
N = 8192
A = torch.randn((N, N), device=device)
B = torch.randn((N, N), device=device)


while True:
    torch.cuda.synchronize()
    start = time.time()
    C = torch.mm(A, B)
    torch.cuda.synchronize()
    end = time.time()

    ops = 2 * N ** 3
    tflops = ops / (end - start) / 1e12
    print(f"Performance: {tflops:.2f} TFLOPS")


