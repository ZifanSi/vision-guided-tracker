// API Types
export type StatusResponse = {
  armed: boolean;
  tilt: number;
  pan: number;
};


export type ApiResponse<T = Record<string, unknown>> = T;


/**
 * API Client for communicating with the Flask backend
 */
export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = "") {
    this.baseUrl = baseUrl;
  }

  /**
   * Sets the base URL for API requests
   */
  setBaseUrl(baseUrl: string): void {
    this.baseUrl = baseUrl;
  }

  /**
   * Automatically creates an ApiClient by trying different base URLs in order.
   * Tests each URL by calling getStatus() and returns the first working instance.
   * @returns Promise resolving to an ApiClient instance with a working base URL
   * @throws Error if none of the base URLs are accessible
   */
  static async createAutomatic(): Promise<ApiClient> {
    const baseUrls = ["", "http://localhost:5000", "http://100.115.14.44"];

    for (const baseUrl of baseUrls) {
      const client = new ApiClient(baseUrl);
      try {
        await client.getStatus();
        console.log(`Connected to API at ${baseUrl}`);
        return client;
      } catch (error) {
        // Continue to next URL if this one fails
        continue;
      }
    }

    throw new Error(
      "Failed to connect to API. Tried base URLs: " + baseUrls.join(", ")
    );
  }

  /**
   * Makes a POST request to the API
   */
  private async post<T>(
    endpoint: string,
    body?: Record<string, unknown>
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      throw new Error(`API request failed: ${response.status} ${response.statusText}`);
    }

    // Handle empty responses
    const text = await response.text();
    if (!text) {
      return {} as T;
    }

    return JSON.parse(text) as T;
  }

  /**
   * Gets the current status from the backend
   * @returns Promise resolving to the status object
   */
  async getStatus(): Promise<ApiResponse<StatusResponse>> {
    return this.post<ApiResponse<StatusResponse>>("/api/status");
  }

  /**
   * Sends a manual move command to the backend
   * @param direction - The direction to move
   * @returns Promise resolving to an empty response
   */
  async manualMove(direction: "up" | "down" | "left" | "right"): Promise<ApiResponse> {
    const body = { direction };
    return this.post<ApiResponse>("/api/manual_move", body);
  }

  /**
   * Sends a manual move to command to the backend
   * @param tilt - The tilt angle to move to
   * @param pan - The pan angle to move to
   * @returns Promise resolving to an empty response
   */
  async manualMoveTo(tilt: number, pan: number): Promise<ApiResponse> {
    const body = { tilt, pan };
    return this.post<ApiResponse>("/api/manual_move_to", body);
  }

  /**
   * Arms the system
   * @returns Promise resolving to an empty response
   */
  async arm(): Promise<ApiResponse> {
    return this.post<ApiResponse>("/api/arm");
  }

  /**
   * Disarms the system
   * @returns Promise resolving to an empty response
   */
  async disarm(): Promise<ApiResponse> {
    return this.post<ApiResponse>("/api/disarm");
  }
}

// Export a default instance
export const apiClient = new ApiClient();

