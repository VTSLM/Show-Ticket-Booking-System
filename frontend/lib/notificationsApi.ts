import { api } from "./api";

export interface NotificationItem {
  id: string;
  event_name: string;
  payload: any;
  read_at: string | null;
  created_at: string;
}

export interface NotificationsResponse {
  notifications: NotificationItem[];
  unread_count: number;
}

export const notificationsApi = {
  list: (limit = 20): Promise<NotificationsResponse> =>
    api.get(`/api/notifications?limit=${limit}`),

  markAsRead: (id: string): Promise<{ status: string }> =>
    api.patch(`/api/notifications/${id}/read`, {}),

  markAllAsRead: (): Promise<{ status: string }> =>
    api.patch(`/api/notifications/read-all`, {}),
};
