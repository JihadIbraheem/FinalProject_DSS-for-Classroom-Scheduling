import React, { useEffect, useState } from 'react';
import axios from 'axios';

function Classrooms() {
    const [classrooms, setClassrooms] = useState([]);

    useEffect(() => {
        axios.get('http://localhost:5000/classrooms')
            .then(response => setClassrooms(response.data))
            .catch(error => console.error(error));
    }, []);

    return (
        <div>
            <h2>רשימת כיתות</h2>
            <ul>
                {classrooms.map(classroom => (
                    <li key={classroom.classroom_id}>
                        {classroom.classroom_num} - קומה {classroom.floor_num}
                    </li>
                ))}
            </ul>
        </div>
    );
}

export default Classrooms;