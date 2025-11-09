import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";

const Dashboard = () => {
  const [devices, setDevices] = useState([]);

  // ✅ Commented these out for now
  // const [activeDeviceId, setActiveDeviceId] = useState(null);
  // const [activeDetails, setActiveDetails] = useState({});

  useEffect(() => {
    const loadDevicesFromJson = async () => {
      try {
        const res = await fetch("/devices.json");
        const data = await res.json();
        setDevices(data.devices);
      } catch (err) {
        console.error("Error loading devices.json:", err);
      }
    };

    loadDevicesFromJson();

    // ✅ Completely disable active-device polling
    /*
    const fetchActiveDevice = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/active");
        const data = await res.json();
        setActiveDeviceId(data.active_id);
        setActiveDetails(data.status || {});
      } catch (err) {
        console.error("Error fetching active device:", err);
      }
    };

    fetchActiveDevice();
    const interval = setInterval(fetchActiveDevice, 3000);
    return () => clearInterval(interval);
    */
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center py-10">
      <h1 className="text-3xl font-bold mb-8">🏠 Smart Home Dashboard</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6 w-11/12">
        {devices.map((device) => {
          
          // ✅ No active check
          // const isActive = device.id === activeDeviceId;

          return (
            <motion.div
              key={device.id}
              className={`rounded-2xl p-4 shadow-lg bg-white border-2`}
              whileHover={{ scale: 1.05 }}

              // ✅ Animations removed because no active device
              // animate={
              //   isActive
              //     ? {
              //         scale: [1, 1.04, 1],
              //         transition: { repeat: Infinity, duration: 1.5 },
              //       }
              //     : {}
              // }
            >
              <div className="flex flex-col items-center">
                
                <img
                  src={`/${device.id}.png`}
                  alt={device.id}
                  className="w-28 h-28 object-contain mb-4"
                  onError={(e) => (e.target.src = "/{device.id}.png")}
                />

                <h2 className="text-xl font-semibold mb-2 text-gray-800">
                  {device.id.replaceAll("_", " ").toUpperCase()}
                </h2>

                <p className="text-sm text-gray-600 mb-2">
                  <b>Functions:</b> {device.functions.join(", ")}
                </p>

                <div className="text-sm text-gray-600 mb-3 text-left w-full">
                  <b>Parameters:</b>
                  <ul className="list-disc ml-5">
                    {Object.entries(device.parameters).map(([key, val]) => (
                      <li key={key}>
                        {key}:{" "}
                        {Array.isArray(val) ? val.join(" - ") : val.toString()}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* ✅ Entire active indicator disabled */}
                {/*
                {isActive && (
                  <motion.div
                    className="bg-blue-100 text-blue-700 px-3 py-1 rounded-lg text-sm text-center mt-2"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.5 }}
                  >
                    ⚙️ Currently Running
                    {Object.keys(activeDetails).length > 0 && (
                      <div className="mt-1 text-xs text-gray-700">
                        {Object.entries(activeDetails).map(([k, v]) => (
                          <div key={k}>
                            {k}: <b>{v}</b>
                          </div>
                        ))}
                      </div>
                    )}
                  </motion.div>
                )}
                */}
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};

export default Dashboard;
