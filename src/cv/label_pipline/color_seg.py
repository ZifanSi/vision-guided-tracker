from sklearn.mixture import GaussianMixture
import cv2
X = cv2.cvtColor(img, cv2.COLOR_BGR2Lab).reshape(-1,3)
gmm = GaussianMixture(n_components=3, covariance_type="full").fit(X)
labels = gmm.predict(X).reshape(img.shape[:2])
