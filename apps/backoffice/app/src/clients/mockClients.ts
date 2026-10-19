export type Client = {
  id: string;
  name: string;
  ico: string;
  dic?: string;
  address?: string;
  status: "active" | "inactive" | "blocked";
};

export const mockClients: Client[] = [
  { id: "c0010000-0000-4000-8000-000000000001", name: "Dravonex Obrábění s.r.o.", ico: "98007009", status: "active" },
  { id: "c0010000-0000-4000-8000-000000000002", name: "Agroluh Vřesava s.r.o.", ico: "98007106", status: "active" },
  { id: "c0010000-0000-4000-8000-000000000003", name: "Kavorin Rec s.r.o.", ico: "98001001", status: "active" },
];
